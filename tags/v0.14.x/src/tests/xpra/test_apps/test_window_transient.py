#!/usr/bin/env python

import gtk

def main():
	window = gtk.Window(gtk.WINDOW_TOPLEVEL)
	window.set_size_request(400, 200)
	window.connect("delete_event", gtk.mainquit)
	vbox = gtk.VBox(False, 0)
	hbox = gtk.HBox(False, 0)
	vbox.pack_start(hbox, expand=False, fill=False, padding=10)

	btn = gtk.Button("Create Transient")
	def create_transient(*args):
		tw = gtk.Window(gtk.WINDOW_TOPLEVEL)
		tw.set_size_request(200, 100)
		tw.connect("delete_event", lambda x,y : tw.destroy())
		tw.set_transient_for(window)
		tw.add(gtk.Label("Transient Window"))
		tw.show_all()
	btn.connect('clicked', create_transient)
	hbox.pack_start(btn, expand=False, fill=False, padding=10)

	btn = gtk.Button("Create Root Transient")
	def create_root_transient(*args):
		tw = gtk.Window(gtk.WINDOW_TOPLEVEL)
		tw.set_size_request(200, 100)
		tw.connect("delete_event", lambda x,y : tw.destroy())
		tw.realize()
		tw.window.set_transient_for(gtk.gdk.get_default_root_window())
		tw.add(gtk.Label("Transient Root Window"))
		tw.show_all()
	btn.connect('clicked', create_root_transient)
	hbox.pack_start(btn, expand=False, fill=False, padding=10)

	window.add(vbox)
	window.show_all()
	gtk.main()
	return 0


if __name__ == "__main__":
	main()
