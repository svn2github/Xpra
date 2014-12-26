#!/usr/bin/env python

import gtk

def main():
	window = gtk.Window(gtk.WINDOW_TOPLEVEL)
	window.set_size_request(200, 300)
	window.connect("delete_event", gtk.mainquit)
	vbox = gtk.VBox(False, 0)

	maximize_btn = gtk.Button("maximize me")
	def maximize(*args):
		window.maximize()
	maximize_btn.connect('clicked', maximize)
	vbox.pack_start(maximize_btn, expand=False, fill=False, padding=10)

	unmaximize_btn = gtk.Button("unmaximize me")
	def unmaximize(*args):
		window.unmaximize()
	unmaximize_btn.connect('clicked', unmaximize)
	vbox.pack_start(unmaximize_btn, expand=False, fill=False, padding=10)

	fullscreen_btn = gtk.Button("fullscreen me")
	def fullscreen(*args):
		window.fullscreen()
	fullscreen_btn.connect('clicked', fullscreen)
	vbox.pack_start(fullscreen_btn, expand=False, fill=False, padding=10)

	unfullscreen_btn = gtk.Button("unfullscreen me")
	def unfullscreen(*args):
		window.unfullscreen()
	unfullscreen_btn.connect('clicked', unfullscreen)
	vbox.pack_start(unfullscreen_btn, expand=False, fill=False, padding=10)

	window.add(vbox)
	window.show_all()
	gtk.main()
	return 0


if __name__ == "__main__":
	main()
