#! /usr/bin/env python3

#       This program is free software; you can redistribute it and/or modify
#       it under the terms of the GNU General Public License as published by
#       the Free Software Foundation; either version 3 of the License, or
#       (at your option) any later version.
#
#       This program is distributed in the hope that it will be useful,
#       but WITHOUT ANY WARRANTY; without even the implied warranty of
#       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#       GNU General Public License for more details.
#
#       You should have received a copy of the GNU General Public License
#       along with this program; if not, write to the Free Software
#       Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#       MA 02110-1301, USA.
"""
Contains code relevant to encoding images and metadata into a djvu format.
"""

import glob
import os
import shutil
import sys
import re
import tempfile
import time
import subprocess

from . import utils


class Encoder:
    """
    An intelligent djvu super-encoder that can work with numerous djvu encoders.
    """

    def __init__(self, opts):
        self.opts = opts

        self.dep_check()
    
    def progress(self):
      pass
    
    def _c44(self, infile, outfile, dpi):
        """
        Encode files with c44.
        """

        # Make sure that the image is in a format acceptable for c44
        extension = infile.split('.')[-1]
        if extension not in ['pgm', 'ppm', 'jpg', 'jpeg']:
            utils.execute('convert {0} {1}'.format(infile, 'temp.ppm'))
            infile = 'temp.ppm'

        # Encode
        cmd = 'c44 -dpi {0} {1} "{2}" "{3}"'.format(dpi, self.opts['c44_options'], infile, outfile)
        utils.execute(cmd)

        # Check that the outfile has been created.
        if not os.path.isfile(outfile):
            msg = 'err: encode.Encoder._c44(): No encode errors, but "{0}" does not exist!'.format(outfile)
            utils.error(msg)
            sys.exit(1)

        # Cleanup
        if (infile == 'temp.ppm') and (os.path.isfile('temp.ppm')):
            os.remove('temp.ppm')

        return None

    def _cjb2(self, infile, outfile, dpi):
        """
        Encode files with cjb2.
        """
        utils.execute('cjb2 -dpi {0} {1} "{2}" "{3}"'.format(dpi, self.opts['cjb2_options'], infile, outfile))

        # Check that the outfile has been created.
        if not os.path.isfile(outfile):
            msg = 'err: encode.Encoder._cpaldjvu(): No encode errors, but "{0}" does not exist!'.format(outfile)
            utils.error(msg)
            sys.exit(1)

        return None

    def _cpaldjvu(self, infile, outfile, dpi):
        """
        Encode files with cpaldjvu.
        """

        # Make sure that the image is in a format acceptable for cpaldjvu
        extension = infile.split('.')[-1]
        
        if extension not in ['ppm']:
            utils.execute('convert {0} {1}'.format(infile, 'temp.ppm'))
            infile = 'temp.ppm'

        # Encode
        utils.execute('cpaldjvu -dpi {0} {1} "{2}" "{3}"'.format(dpi, self.opts['cpaldjvu_options'], infile, outfile))

        # Check that the outfile has been created.
        if not os.path.isfile(outfile):
            msg = 'err: encode.Encoder._cpaldjvu(): No encode errors, but "{0}" does not exist!'.format(outfile)
            utils.error(msg)
            sys.exit(1)

        # Cleanup
        if (infile == 'temp.ppm') and (os.path.isfile('temp.ppm')):
            os.remove('temp.ppm')

        return None

    def _csepdjvu(self, infile, outfile, dpi):
        """
        Encode files with csepdjvu.
        """
        
        temp_graphics1 = tempfile.NamedTemporaryFile(delete=False, suffix='.tif')
        temp_graphics2 = tempfile.NamedTemporaryFile(delete=False, suffix='.ppm')
        
        temp_graphics1.close()
        temp_graphics2.close()
        
        temp_textual1 = tempfile.NamedTemporaryFile(delete=False, suffix='.tif')
        temp_textual2 = tempfile.NamedTemporaryFile(delete=False, suffix='.rle')
        
        temp_textual1.close()
        temp_textual2.close()
        
        # Separate the bitonal text (scantailor's mixed mode) from everything else.
        utils.execute('convert -opaque black "{0}" "{1}"'.format(infile, temp_graphics1.name))
        utils.execute('convert +opaque black "{0}" "{1}"'.format(infile, temp_textual1.name))
        
        enc_bitonal_out = tempfile.NamedTemporaryFile(delete=False, suffix='.djvu')
        enc_bitonal_out.close()
        
        # Encode the bitonal image.
        self._cjb2(temp_textual1.name, enc_bitonal_out.name, dpi)

        # Encode with color with bitonal via csepdjvu
        utils.execute('ddjvu -format=rle -v "{0}" "{1}"'.format(enc_bitonal_out.name, re.sub('\.tif$', '.rle', temp_textual2.name)))
        utils.execute('convert "{0}" "{1}"'.format(temp_graphics1.name, temp_graphics2.name))
        
        temp_merge = tempfile.NamedTemporaryFile(delete=False, suffix='.mix')
        temp_merge.close()
        
        with open(temp_merge.name, 'wb') as mix:
            with open(temp_textual2.name, 'rb') as rle:
                buffer = rle.read(1024)
                while buffer:
                    mix.write(buffer)
                    buffer = rle.read(1024)
            with open(temp_graphics2.name, 'rb') as ppm:
                buffer = ppm.read(1024)
                while buffer:
                    mix.write(buffer)
                    buffer = ppm.read(1024)
        
        temp_final = tempfile.NamedTemporaryFile(delete=False)
        temp_final.close()

        utils.execute('csepdjvu -d {0} {1} "{2}" "{3}"'.format(dpi, self.opts['csepdjvu_options'], temp_merge.name, temp_final.name))

        if not os.path.isfile(outfile):
            shutil.copy(temp_final.name, outfile)
        else:
            utils.execute('djvm -i {0} "{1}"'.format(outfile, temp_final.name))
        
        for temp in [temp_graphics1, temp_graphics2, temp_textual1, temp_textual2, enc_bitonal_out, temp_merge, temp_final]:
          os.remove(temp.name)

        return None

    def _minidjvu(self, infiles, outfile, dpi):
        """
        Encode files with minidjvu.
        N.B., minidjvu is the only encoder function that expects a list a filenames
        and not a string with a single filename.  This is because minidjvu gains
        better compression with a shared dictionary across multiple images.
        """

        # Specify filenames that will be used.
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.djvu')
        temp_file.close()

        # Minidjvu has to worry about the length of the command since all the filenames are
        # listed.
        cmds = utils.split_cmd('minidjvu -d {0} {1}'.format(dpi, self.opts['minidjvu_options']), infiles, temp_file.name)

        # Execute each command, adding each result into a single, multipage djvu.
        for cmd in cmds:
            utils.execute(cmd)
            self.djvu_insert(temp_file.name, outfile)

        os.remove(tempfile.name)

        return None

    def dep_check(self):
        """
        Check for ocr engine availability.
        """

        if not utils.is_executable(self.opts['bitonal_encoder']):
            msg = 'err: encoder "{0}" is not installed.'.format(self.opts['bitonal_encoder'])
            utils.error(msg)
            sys.exit(1)
        if not utils.is_executable(self.opts['color_encoder']):
            msg = 'err: encoder "{0}" is not installed.'.format(self.opts['color_encoder'])
            utils.error(msg)
            sys.exit(1)

        return None

    def djvu_insert(self, infile, djvufile, page_num=None):
        """
        Insert a single page djvu file into a multipage djvu file.  By default it will be
        placed at the end, unless page_num is specified.
        """
        if (not os.path.isfile(djvufile)):
            shutil.copy(infile, djvufile)
        elif page_num is None:
            utils.execute('djvm -i "{0}" "{1}"'.format(djvufile, infile))
        else:
            utils.execute('djvm -i "{0}" "{1}" {2}'.format(djvufile, infile, int(page_num)))

    def enc_book(self, book, outfile):
        """
        Encode pages, metadata, etc. contained within a organizer.Book() class.
        """

        temp_book = tempfile.NamedTemporaryFile(delete=False, suffix='.djvu')
        temp_book.close()

        # Encode bitonal images first, mainly because of minidjvu needing to do
        # them all at once.
        if self.opts['bitonal_encoder'] == 'minidjvu':
            bitonals = []
            for page in book.pages:
                if page.bitonal:
                    bitonals.append(page.path)
            if len(bitonals) > 0:
                if self.opts['bitonal_encoder'] == 'minidjvu':
                    self._minidjvu(bitonals, temp_book.name, book.dpi)
                    self.djvu_insert(temp_book.name, outfile)
                    utils.error('asd')
                    os.remove(temp_book.name)
                    self.progress()
        elif self.opts['bitonal_encoder'] == 'cjb2':
            for page in book.pages:
                if page.bitonal:
                    self._cjb2(page.path, temp_book.name, page.dpi)
                    self.djvu_insert(temp_book.name, outfile)
                    os.remove(temp_book.name)
                    self.progress()
        else:
            for page in book.pages:
                if not page.bitonal:
                    msg = 'wrn: Invalid bitonal encoder.  Bitonal pages will be omitted.'
                    msg = utils.color(msg, 'red')
                    utils.error(msg)
                    break

        # Encode and insert non-bitonal
        if self.opts['color_encoder'] == 'csepdjvu':
            for page in book.pages:
                if not page.bitonal:
                    page_number = book.pages.index(page) + 1
                    self._csepdjvu(page.path, temp_book.name, page.dpi)
                    self.djvu_insert(temp_book.name, outfile, page_number)
                    os.remove(temp_book.name)
                    self.progress()
        elif self.opts['color_encoder'] == 'c44':
            for page in book.pages:
                if not page.bitonal:
                    page_number = book.pages.index(page) + 1
                    self._c44(page.path, temp_book.name, page.dpi)
                    self.djvu_insert(temp_book.name, outfile, page_number)
                    os.remove(temp_book.name)
                    self.progress()
        elif self.opts['color_encoder'] == 'cpaldjvu':
            for page in book.pages:
                if not page.bitonal:
                    page_number = book.pages.index(page) + 1
                    self._cpaldjvu(page.path, temp_book.name, page.dpi)
                    self.djvu_insert(temp_book.name, outfile, page_number)
                    os.remove(temp_book.name)
                    self.progress()
        else:
            for page in book.pages:
                if not page.bitonal:
                    msg = 'wrn: Invalid color encoder.  Colored pages will be omitted.'
                    msg = utils.color(msg, 'red')
                    utils.error(msg)
                    break

        # Add ocr data
        if self.opts['ocr']:
            for page in book.pages:
                handle = open('ocr.txt', 'w', encoding="utf8")
                handle.write(page.text)
                handle.close()
                page_number = book.pages.index(page) + 1
                utils.simple_exec('djvused -e "select {0}; remove-txt; set-txt \'ocr.txt\'; save" "{1}"'.format(page_number, outfile))
                os.remove('ocr.txt')

        # Insert front/back covers, metadata, and bookmarks
        if book.suppliments['cover_front'] is not None:
            dpi = int(utils.execute('identify -ping -format %x "{0}"'.format(book.suppliments['cover_front']), capture=True).decode('ascii').split(' ')[0])
            self._c44(book.suppliments['cover_front'], temp_book.name, dpi)
            self.djvu_insert(temp_book.name, outfile, 1)
            utils.execute('djvused -e "select 1; set-page-title cover; save" "{0}"'.format(outfile))
        if book.suppliments['cover_back'] is not None:
            dpi = int(utils.execute('identify -ping -format %x "{0}"'.format(book.suppliments['cover_back']), capture=True).decode('ascii').split(' ')[0])
            self._c44(book.suppliments['cover_back'], temp_book.name, dpi)
            self.djvu_insert(temp_book.name, outfile, -1)
        if book.suppliments['metadata'] is not None:
            utils.simple_exec('djvused -e "set-meta {0}; save" "{1}"'.format(book.suppliments['metadata'], outfile))
        if book.suppliments['bookmarks'] is not None:
            utils.simple_exec('djvused -e "set-outline {0}; save" "{1}"'.format(book.suppliments['bookmarks'], outfile))

        script = ''
        index = 1
        if book.suppliments['cover_front'] is not None:
            script += 'select '+str(index)+'; set-page-title "cover";\n'
            index = index + 1
        for page in book.pages:
            if page.title is None:
                index = index + 1
            else:
                script += 'select '+str(index)+'; set-page-title "'+str(page.title)+'";\n'
                index = index + 1
        if book.suppliments['cover_back'] is not None:
            script += 'select '+str(index)+'; set-page-title "back cover";\n'
        script += 'save'
        with open('titles', 'w') as handle:
            handle.write(script)
        utils.simple_exec('djvused -f titles "{0}"'.format(outfile))
        os.remove('titles')

        if os.path.isfile(temp_book.name):
            os.remove(temp_book)

        return None
