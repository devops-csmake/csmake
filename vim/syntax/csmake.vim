"# <copyright>
"# (c) Copyright 2017 Hewlett Packard Enterprise Development LP
"#
"# This program is free software: you can redistribute it and/or modify it
"# under the terms of the GNU General Public License as published by the
"# Free Software Foundation, either version 3 of the License, or (at your
"# option) any later version.
"#
"# This program is distributed in the hope that it will be useful,
"# but WITHOUT ANY WARRANTY; without even the implied warranty of
"# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
"# Public License for more details.
"#
"# You should have received a copy of the GNU General Public License
"# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"# </copyright>

" Vim syntax file
" Language:               Configuration File (ini file) for MSDOS/MS Windows
" Version:                2.1
" Original Author:        Sean M. McKee <mckee@misslink.net>
" Previous Maintainer:    Nima Talebi <nima@it.net.au>
" Current Maintainer:     Hong Xu <xuhdev@gmail.com>
" Homepage:               http://www.vim.org/scripts/script.php?script_id=3747
"                         https://bitbucket.org/xuhdev/syntax-dosini.vim
" Last Change:            2011 Nov 8


" For version 5.x: Clear all syntax items
" For version 6.x: Quit when a syntax file was already loaded
if version < 600
  syntax clear
elseif exists("b:current_syntax")
  finish
endif

" shut case off
syn case ignore

syn match  csmakeNumber   "\<\d\+\>"
syn match  csmakeNumber   "\<\d*\.\d\+\>"
syn match  csmakeNumber   "\<\d\+e[+-]\=\d\+\>"
syn match  csmakeLabel    "^[^*\t ].*="
syn match  csmakeSystemLabel "^\*\*.*="
syn match  csmakeId       "@[^\]]*" contained
syn region csmakeHeader   start="^\s*\[" end="\]" contains=csmakeId
syn match  csmakeComment  "^[#;].*$"

" Define the default highlighting.
" For version 5.7 and earlier: only when not done already
" For version 5.8 and later: only when an item doesn't have highlighting yet
if version >= 508 || !exists("did_csmake_syntax_inits")
  if version < 508
    let did_csmake_syntax_inits = 1
    command -nargs=+ HiLink hi link <args>
  else
    command -nargs=+ HiLink hi def link <args>
  endif

"  HiLink csmakeNumber   Number
  HiLink csmakeHeader   Keyword
  HiLink csmakeComment  Comment
  HiLink csmakeLabel    Type
  HiLink csmakeSystemLabel    Function
  HiLink csmakeId       Special

  delcommand HiLink
endif

let b:current_syntax = "csmake"

" vim: sts=2 sw=2 et
