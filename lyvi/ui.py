# Copyright (c) 2013 Ondrej Kipila <ok100 at lavabit dot com>
# This work is free. You can redistribute it and/or modify it under the
# terms of the Do What The Fuck You Want To Public License, Version 2,
# as published by Sam Hocevar. See the COPYING file for more details.

import urwid

import lyvi


class MyListBox(urwid.ListBox):
    signals = ['changed']

    def mouse_event(self, size, event, button, col, row, focus):
        if event == 'mouse press':
            if button == 4:
                self.keypress(size, 'up')
                return True
            if button == 5:
                self.keypress(size, 'down')
                return True
        return self.__super.mouse_event(size, event, button, col, row, focus)

    def keypress(self, size, key):
        if key == 'g':
            self.set_focus(0)
            return True
        if key == 'G':
            self.set_focus(len(self.body) - 1)
            self.set_focus_valign('bottom')
            return True
        return self.__super.keypress(size, key)

    def calculate_visible(self, size, focus=False):
        width, height = size
        middle, top, bottom = self.__super.calculate_visible(size, focus)
        fpos = self.body.index(top[1][-1][0]) if top[1] else self.focus_position
        top_line = sum([self.body[n].rows((width,)) for n in range(0, fpos)]) + top[0]
        total_lines = sum([widget.rows((width,)) for widget in self.body])
        if total_lines <= height:
            self.pos = 'All'
        elif top_line == 0:
            self.pos = 'Top'
        elif top_line + height == total_lines:
            self.pos = 'Bot'
        else:
            self.pos = '%d%%' % round(top_line * 100 / (total_lines - height))
        self._emit('changed')
        return middle, top, bottom


class Ui:
    def init(self):
        self.views = ['lyrics', 'artistbio', 'guitartabs']
        for view in self.views:
            setattr(self, view, None)
        self.artist = None
        self.title = None
        self.album = None
        self.view = lyvi.config['default_view']
        self.hidden = lyvi.config['ui_hidden']

        self.header = urwid.Text(('header', ''))
        self.statusbar = urwid.AttrMap(urwid.Text('', align='right'), 'statusbar')
        self.content = urwid.SimpleListWalker([urwid.Text(('content', ''))])
        self.listbox = MyListBox(self.content)

        palette = [
            ('header', lyvi.config['header_fg'], lyvi.config['header_bg']),
            ('content', lyvi.config['text_fg'], lyvi.config['text_bg']),
            ('statusbar', lyvi.config['statusbar_fg'], lyvi.config['statusbar_bg']),
        ]
        self.frame = urwid.Frame(urwid.Padding(self.listbox, left=1, right=1),
            footer=self.statusbar)

        urwid.connect_signal(self.listbox, 'changed', self.update_statusbar)

        self.loop = urwid.MainLoop(self.frame, palette, unhandled_input=self.input)
        self.update()

    def set_header(self, header):
        if not self.hidden:
            self.header.set_text(('header', header))

    def set_text(self, text):
        if not self.hidden:
            self.content[:] = [self.header, urwid.Divider()] + \
                [urwid.Text(('content', line)) for line in text.splitlines()]

    def update(self):
        if lyvi.player.status == 'stopped':
            self.set_header('N/A' if self.view == 'artistbio' else 'N/A - N/A')
            self.set_text('Not playing')
        elif self.view == 'lyrics':
            self.set_header('%s - %s' % (self.artist or 'N/A', self.title or 'N/A'))
            self.set_text(self.lyrics or 'No lyrics found')
        elif self.view == 'artistbio':
            self.set_header(self.artist or 'N/A')
            self.set_text(self.artistbio or 'No artist info found')
        elif self.view == 'guitartabs':
            self.set_header('%s - %s' % (self.artist or 'N/A', self.title or 'N/A'))
            self.set_text(self.guitartabs or 'No guitar tabs found')
        self.refresh()

    def refresh(self):
        self.loop.draw_screen()

    def home(self):
        """Scroll to the top of the ListBox"""
        self.listbox.set_focus(0)
        self.refresh()

    def update_statusbar(self, x=None):
        if not self.hidden:
            text = urwid.Text('%s%s' % (self.view, self.listbox.pos.rjust(10)), align='right')
            wrap = urwid.AttrWrap(text, 'statusbar')
            self.frame.set_footer(wrap)

    def toggle_views(self, x=None):
        """Toggle between views"""
        if not self.hidden:
            n = self.views.index(self.view)
            self.view = self.views[n + 1] if n < len(self.views) - 1 else self.views[0]
            self.home()
            self.update()

    def toggle_visibility(self):
        if lyvi.bg:
            if not self.hidden:
                self.set_header('')
                self.set_text('')
                self.frame.set_footer(urwid.AttrWrap(urwid.Text(''), 'statusbar'))
                lyvi.bg.opacity = 1.0
                lyvi.bg.update()
                self.hidden = True
            else:
                self.hidden = False
                self.update()
                lyvi.bg.opacity = lyvi.config['bg_opacity']
                lyvi.bg.update()

    def reload_view(self):
        """Reload current view"""
        if not ((self.view == 'artistbio' and self.artist) or (self.artist and self.title)):
            return
        from threading import Thread
        import lyvi.metadata
        self.home()
        text = 'Searching %s...' % \
            ('artist info' if self.view == 'artistbio' else
            'guitar tabs' if self.view == 'guitartabs' else self.view)
        setattr(self, self.view, text)
        self.update()
        lyvi.metadata.cache_delete(self.view, self.artist, self.title, self.album)
        worker = Thread(target=lyvi.metadata.get_and_update,
            args=(self.view, self.artist, self.title, self.album))
        worker.daemon = True
        worker.start()
        
    def input(self, key):
        import lyvi
        if key == lyvi.config['key_quit']:
            self.exit()
        elif key == lyvi.config['key_toggle_views']:
            self.toggle_views()
        elif key == lyvi.config['key_reload_view']:
            self.reload_view()
        elif key == lyvi.config['key_toggle_bg_type']:
            lyvi.bg.toggle_type()
        elif key == lyvi.config['key_hide_ui']:
            self.toggle_visibility()

    def exit(self):
        """Quit"""
        raise urwid.ExitMainLoop()
