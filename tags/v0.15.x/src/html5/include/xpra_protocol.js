/*
 * Copyright (c) 2013 Antoine Martin <antoine@devloop.org.uk>
 * Copyright (c) 2014 Joshua Higgins <josh@kxes.net>
 * Copyright (c) 2015 Spikes, Inc.
 * Portions based on websock.js by Joel Martin
 * Copyright (C) 2012 Joel Martin
 *
 * Licensed under MPL 2.0
 *
 * xpra wire protocol with worker support
 *
 * requires:
 *	bencode.js
 *  inflate.js
 */


/*
A stub class to facilitate communication with the protocol when
it is loaded in a worker
*/
function XpraProtocolWorkerHost() {
	this.worker = null;
	this.packet_handler = null;
	this.packet_ctx = null;
}

XpraProtocolWorkerHost.prototype.open = function(uri) {
	var me = this;
	this.worker = new Worker('include/xpra_protocol.js');
	this.worker.addEventListener('message', function(e) {
		var data = e.data;
		switch (data.c) {
			case 'r':
				me.worker.postMessage({'c': 'o', 'u': uri});
				break;
			case 'p':
				if(me.packet_handler) {
					me.packet_handler(data.p, me.packet_ctx);
				}
				break;
			case 'l':
				console.log(data.t);
				break;
		default:
			console.error("got unknown command from worker");
			console.error(e.data);
		};
	}, false);
}

XpraProtocolWorkerHost.prototype.close = function() {
	this.worker.postMessage({'c': 'c'});
}

XpraProtocolWorkerHost.prototype.send = function(packet) {
	this.worker.postMessage({'c': 's', 'p': packet});
}

XpraProtocolWorkerHost.prototype.set_packet_handler = function(callback, ctx) {
	this.packet_handler = callback;
	this.packet_ctx = ctx;
}


/*
The main Xpra wire protocol
*/
function XpraProtocol() {
	this.packet_handler = null;
	this.packet_ctx = null;
	this.websocket = null;
	this.raw_packets = [];
	this.mode = 'binary';  // Current WebSocket mode: 'binary', 'base64'
    this.rQ = [];          // Receive queue
    this.rQi = 0;          // Receive queue index
    this.rQmax = 10000;    // Max receive queue size before compacting
    this.sQ = [];          // Send queue
}

XpraProtocol.prototype.open = function(uri) {
	var me = this;
	// init
	this.rQ         = [];
    this.rQi        = 0;
    this.sQ         = [];
    this.websocket  = null;
    // connect the socket
    this.websocket = new WebSocket(uri, 'binary');
	this.websocket.binaryType = 'arraybuffer';
	this.websocket.onopen = function () {
		me.packet_handler(['open'], me.packet_ctx);
	};
	this.websocket.onclose = function () {
		me.packet_handler(['close'], me.packet_ctx);
	};
	this.websocket.onerror = function () {
		me.packet_handler(['error'], me.packet_ctx);
	};
	this.websocket.onmessage = function (e) {
		// push arraybuffer values onto the end
        var u8 = new Uint8Array(e.data);
        for (var i = 0; i < u8.length; i++) {
            me.rQ.push(u8[i]);
        }
        // wait for 8 bytes
        if (me.rQ.length >= 8) {
	        me._process();
	    }
	};
}

XpraProtocol.prototype.close = function() {
	this.websocket.close();
}

XpraProtocol.prototype.send = function(packet) {
	//debug("send worker:"+packet);
	var bdata = bencode(packet);
	//convert string to a byte array:
	var cdata = [];
	for (var i=0; i<bdata.length; i++)
		cdata.push(ord(bdata[i]));
	var level = 0;
	/*
	var use_zlib = false;		//does not work...
	if (use_zlib) {
		cdata = new Zlib.Deflate(cdata).compress();
		level = 1;
	}*/
	var len = cdata.length;
	//struct.pack('!BBBBL', ord("P"), proto_flags, level, index, payload_size)
	var header = ["P".charCodeAt(0), 0, level, 0];
	for (var i=3; i>=0; i--)
		header.push((len >> (8*i)) & 0xFF);
	//concat data to header, saves an intermediate array which may or may not have
	//been optimised out by the JS compiler anyway, but it's worth a shot
	header = header.concat(cdata);
	//debug("send("+packet+") "+data.byteLength+" bytes in packet for: "+bdata.substring(0, 32)+"..");
	// put into buffer before send
	this.websocket.send((new Uint8Array(header)).buffer);
}

XpraProtocol.prototype.set_packet_handler = function(callback, ctx) {
	this.packet_handler = callback;
	this.packet_ctx = ctx;
}

XpraProtocol.prototype._buffer_peek = function(bytes) {
	return this.rQ.slice(0, 0+bytes);
}

XpraProtocol.prototype._buffer_shift = function(bytes) {
	return this.rQ.splice(0, 0+bytes);;
}

XpraProtocol.prototype._process = function() {
	// peek at first 8 bytes of buffer
	var buf = this._buffer_peek(8);

	if (buf[0]!=ord("P")) {
		msg = "invalid packet header format: " + buf[0];
		if (buf.length>1) {
			msg += ": ";
			for (c in buf) {
				msg += String.fromCharCode(c);
			}
		}
		throw msg;
	}

	var proto_flags = buf[1];
	if (proto_flags!=0) {
		throw "we cannot handle any protocol flags yet, sorry";
	}
	var level = buf[2];
	var index = buf[3];
	var packet_size = 0;
	for (var i=0; i<4; i++) {
		//debug("size header["+i+"]="+buf[4+i]);
		packet_size = packet_size*0x100;
		packet_size += buf[4+i];
	}
	//debug("packet_size="+packet_size+", level="+level+", index="+index);

	// wait for packet to be complete
	// the header is still on the buffer so wait for packetsize+headersize bytes!
	if (this.rQ.length < packet_size+8) {
		// we already shifted the header off the buffer?
		debug("packet is not complete yet");
		return;
	}

	// packet is complete but header is still on buffer
	this._buffer_shift(8);
	//debug("got a full packet, shifting off "+packet_size);
	var packet_data = this._buffer_shift(packet_size);

	//decompress it if needed:
	if (level!=0) {
		if (level & 0x10) {
			// lz4
			// python-lz4 inserts the length of the uncompressed data as an int
			// at the start of the stream
			var d = packet_data.splice(0, 4);
			// will always be little endian
			var length = d[0] | (d[1] << 8) | (d[2] << 16) | (d[3] << 24);
			// decode the LZ4 block
			var inflated = new Buffer(length);
			var uncompressedSize = LZ4.decodeBlock(packet_data, inflated);
			inflated = inflated.slice(0, uncompressedSize);
		} else if (level & 0x20) {
			// lzo
		} else {
			// zlib
			var inflated = new Zlib.Inflate(packet_data).decompress();
		}
		//debug("inflated("+packet_data+")="+inflated);
		packet_data = inflated;
	}
	
	//save it for later? (partial raw packet)
	if (index>0) {
		//debug("added raw packet for index "+index);
		this.raw_packets[index] = packet_data;
	} else {
		//decode raw packet string into objects:
		var packet = null;
		try {
			packet = bdecode(packet_data);
			for (var index in this.raw_packets) {
				packet[index] = this.raw_packets[index];
			}
			this.raw_packets = {}
			// pass to our packet handler
			this.packet_handler(packet, this.packet_ctx);
		}
		catch (e) {
			console.error("error processing packet " + e)
			//console.error("packet_data="+packet_data);
		}
	}

	// see if buffer still has unread packets
	if (this.rQ.length >= 8) {
		this._process();
	}

}


/*
If we are in a web worker, set up an instance of the protocol
*/
if (!(typeof window == "object" && typeof document == "object" && window.document === document)) {
	// some required imports
	// worker imports are relative to worker script path
	importScripts('websock.js',
		'bencode.js',
		'inflate.min.js',
		'lz4.min.js');
	// make protocol instance
	var protocol = new XpraProtocol();
	// we create a custom packet handler which posts packet as a message
	protocol.set_packet_handler(function (packet, ctx) {
		postMessage({'c': 'p', 'p': packet});
	}, null);
	// attach listeners from main thread
	self.addEventListener('message', function(e) {
		var data = e.data;
		switch (data.c) {
		case 'o':
			protocol.open(data.u);
			break;
		case 's':
			protocol.send(data.p)
			break;
		case 'c':
			// terminate the worker
			protocol.close();
			self.close();
			break;
		default:
			postMessage({'c': 'l', 't': 'got unknown command from host'});
		};
	}, false);
	// tell host we are ready
	postMessage({'c': 'r'});
}


// initialise LZ4 library
var Buffer = require('buffer').Buffer;
var LZ4 = require('lz4');