# csmake
Completely Specified Make (csmake) tool - modular build scripting tool

# Quick Start
If you check out the project from git, you can run:

	`./csmake --help-long`

to get the list of flags you can pass csmake.  You can then run:

	`./csmake --list-phases

to see the different phases the tool can utilize for the current build environment.
One phase you'll see is `test`.  Go ahead and run:
	`./csmake test





# Overview and Motivation
Most build tools (such as make, ant, maven, etc.) are centered around the idea
of delivering one or a handful of results (build artefacts) based around a
small set of tools or a single development path.  In practice, what we find
are a couple of consequences because of this.  First, there are many things
these build tools "know" how to do intrinsically.  In other words, they are
built around the 80% of projects that will follow a particular
build/development sequence.  While these intrinsic pieces are helpful to
developers in the tool's sweet spot, often these tend to get in the way of
understanding of the build specification, maintainability of the build
specification, and the ability to add more automated processes to the tooling
that fall soundly outside of the sweet spot.  Second, a given build tool only
handles one or a couple of parts of the product lifecycle, leaving users to
need other tools to automate other pieces of the process (usually shell
scripts - if anything at all).

Consider, if make sufficed for all building processes for all time and
eternity, why does ant or maven exist?  If make covered enough steps of the
entire development cycle, why does scons and automake exist?  One could simply
argue (incorrectly) that this is duplication of effort, the authors didn't
want to take the time to learn the tool so they recapitulated it.  It's clear
to see, given the popularity of ant and maven in some development circles
(namely Java, which is their sweet spot), that make either didn't suffice for
the needs of these developers, or these tools surpassed make in some way to
make their jobs easier.  In fact, if we look beyond compiled languages to
Python, Ruby, etc. we find that we diverge greatly from the traditional
developer workflow tools.  I'll pick on Python because the state of affairs
here is the bleakest (but rake for Ruby exists, let's not forget...).
Distutils, setuptools, pip, virtualenv, setup.py, TOX, unittest, PyPI, Wheels,
Eggs, PEPs overriding other PEPs on things like tracking installation of
python modules, and on it goes, a never-ending march to reimplement every
other conceivable tool, wrapper, concept to fit everything you could ever
possibly conceive of doing - until the new next thing is conceived - something
these tools don't yet support like - gasp - delivering a man page?  Good
luck... Python developers have recapitulated the problem of tool
specialization in spades.  All these various build/developer tools all solve
specific problems and like make, ant, etc., and all have been pushed and
stretched way beyond their sweet spots (e.g., using pip for production
builds - in my option this was never Mr. Bicking's purpose for pip).  When it comes to
packaging, forget about it - every format has a very specific tool chain and an
environment required for building - and cross platform or even distros - well,
you're signing up for a lot of hardship and brain damage - not to mention
reading, lots and lots of reading.

So, is the alternative a tool that is so generic it does nothing at all?
Isn't that the rub?  What if the answer was almost yes?  Enter, csmake.

csmake provides a developer four basic pieces that every product large and
small needs:
    - A means to specify the build - csmake uses (abuses) the Python (ne
Windows) ini format.
    - A way to say what you are building - csmake provides support for metadata
natively
    - A way to track files through a build process - csmake provides a way to
annotate steps (sections) with file tracking and doesn't require that sections
participate in the tracking
    (In other words, file tracking is informative, orthogonal, and optional
unless your module(s) use the file tracking information directly)
    - A way to easily implement custom steps - csmake is extremely modular, so
much so that almost everything is a module (there's your almost
nothing....without any modules csmake literally does nothing).
csmake also provides a developer some modern conveniences:
    - Similar to maven's idea of workflow, csmake has phases and sequences of
phases
    - Unlike maven's idea of workflow, csmake's phases and order are not
dictated by the tool
    - Similar to make's idea of commands or entry points, csmake has commands
(and "multicommands" so you can essentially build an ad-hoc command on the
command-line)
    - Similar to make's (and most build tools) idea of context sensitive
execution, csmake uses the "csmakefile" in the current working directory
(barring further direction)
    - Similar to most build tools, csmake can do what most developers would
need, or expect if they just typed the command "csmake", provided the
csmakefile defines the proper default behaviors
    - Modules and builds are self-documenting - the documentation is available
from the command-line
    (--help, --help --verbose, --list-phases, --list-commands, --list-type,
--list-types)
    - Modules are object-oriented (full python classes and objects)
    - It's quite simple to deliver a library of csmake modules
    - Modules can be defined as aspects that participate in join points and
control flow - providing for separation of concerns and builds that can self-
heal
    (Example: I have a flaky git....ok, create an aspect that will catch a git
failure and try it again in some cases - no changes to the actual git module
required)
    (Example: I have a problem where I need to temporarily add configuration
with a shell script before I execute a section but I can't let it linger for
the whole build - ok, decorate the section with a ShellAspect that modifies
the configuration at the start of the section and changes it back at the end -
again, no changes to the module required)

With this flexibility csmakefiles have been written that:
    - Recreate diskimage-builder in such a manner that the build process was so
flexible, new steps could be added, builds could be halted and reused half way
though the process, and steps like pushing builds to archives could be added
to a singular build process.
    - Packaging libraries as debs (and tarballs, and wheels, and soon...rpms)
using the same tooling (the csmake installmap and Packager modules)
    - Also, the packaging is part of the build process.  (e.g., csmake build
test package - would build, then test, then package the results)
    - Builds full vm images without the use of a tool like diskimage-builder
(and archives the results, etc.)
    - Generates the proper file staging, renaming, and xml description for HP's
SMTA delivery process
    - Manages expiration and storage (e.g. user access) policy for artefact
storage that can be enforced by a build directly or by a "centurion" script
that will reset the policy separate from the build
    - Allow artefacts to be managed and "binned" in the storage based on quality
testing (i.e., promotion scripts).
    - Packages virtualenvs as a tarball (and would also package them as a debian
if desired with almost no configuration changes).
The next sections go into greater details on each of the points above.

## csmake Build Configurations - csmakefiles
A csmakefile is simply a csmake build configuration in a python ini format
that calls out the various modules that will be used to perform a build.  Each
section (except for the [\~\~phases\~\~] section) is a reference to a module

For example:
```
[~~phases~~]
build=Build the csmake example
**default=build

[command@my-command]
0000=do-hello

[Shell@do-hello]
command=set -eux
   echo "Hello"
   echo "World"
```

This csmakefile has three sections, one is the special "phases" section, and
two other sections.  The section header contains a label which calls out the
module that should be executed, e.g., "command" and "Shell", an '@' symbol,
followed by an identifier for the section, e.g., "my-command" and "do-hello".
csmake will execute "command" sections from the command-line.  If a specific
command isn't called out on the command line, csmake will look for a default
command section (either [command@] or [command@default]) failing that, it will
pick a command section to execute.  The modules define what key/value pairs
should be used with the section.  As you can see from the example above,
python ini is fairly free-flowing, allowing multi-line values, providing a
free flowing form for things like specifying short shell scripts for example.
You can see what a specific module expects for key/value pairs by typing:
csmake --list-command=Shell, for example, which would give you the module
documentation for Shell.

So, if the above csmakefile was in your current working directory and you type
the command:
```
csmake
```

You would get several "chunks" of output

```
% csmake
 ___  ______  ______  ______  ______  ______  ______  ______  ______  ___
  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__
 (______)(______)(______)(______)(______)(______)(______)(______)(______)
     Begin csmake - version 1.5.7
------------------------------------------------------------------
       _   _   _   _   _   _   _   _   _   _   _   _   _   _   _   _
    ,-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)
    `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-'
         BEGINNING PHASE: build
             Build the csmake example
__________________________________________________________________
  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (
------------------------------------------------------------------
+ command@my-command      ---  Begin
------------------------------------------------------------------
__________________________________________________________________
  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (  (
------------------------------------------------------------------
++ Shell@do-hello      ---  Begin
------------------------------------------------------------------
+ echo Hello
Hello
+ echo World
World
------------------------------------------------------------------
 nununununununununununun   Step: Passed   nununununununununununun
------------------------------------------------------------------
++ Shell@do-hello      ---  End
------------------------------------------------------------------
__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)
------------------------------------------------------------------
 nununununununununununun   Step: Passed   nununununununununununun
------------------------------------------------------------------
+ command@my-command      ---  End
------------------------------------------------------------------
__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)__)
         ENDING PHASE: build
             Build the csmake example
       _   _   _   _   _   _   _   _   _   _   _   _   _   _   _   _
    ,-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)-(_)
    `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-' `-'
   SEQUENCE EXECUTED: build
     Build the csmake example
------------------------------------------------------------------
  .--.      .--.      .--.      .--.      .--.      .--.      .--.      .
:::::.\::::::::.\::::::::.\::::::::.\::::::::.\::::::::.\::::::::.\::::::
'      `--'      `--'      `--'      `--'      `--'      `--'      `--'
     csmake: Passed
------------------------------------------------------------------
     End csmake - version 1.5.7
------------------------------------------------------------------
 ___  ______  ______  ______  ______  ______  ______  ______  ______  ___
  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__  __)(__
 (______)(______)(______)(______)(______)(______)(______)(______)(______)
```

If you use the "quiet" flag, you just get the shell output:
```
% csmake --quiet
+ echo Hello
Hello
+ echo World
World
```

Or if you use the "no-chatter" flag, you just get the bare bones "signposts"
for each block of execution:
```
% csmake --no-chatter
     Begin csmake - version 1.5.7
         BEGINNING PHASE: build
             Build the csmake example
+ command@my-command      ---  Begin
++ Shell@do-hello      ---  Begin
+ echo Hello
Hello
+ echo World
World
++ Step Status: Passed
++ Shell@do-hello      ---  End
+ Step Status: Passed
+ command@my-command      ---  End
         ENDING PHASE: build
             Build the csmake example
   SEQUENCE EXECUTED: build
     Build the csmake example
 Step Status: Passed
     End csmake - version 1.5.7
```

## Metadata in csmake
Unless a build is constructed "just for fun", builds are created for the
purpose of delivering some kind of "product" which could be an open source
developer delivering their library, or a company delivering an installable
software solution to their customers.  csmake recognizes the problems that
arise when there is no consistent way to communicate the metadata of a
product, such as the current version, the name or description of the product.
csmake defines a "metadata" module and implements internal tracking of this
metadata.  In fact, the philosophy of using metadata tied to the build is so
key in csmake that the file tracking capabilities in csmake are also coupled
with the metadata, and of course some builds may actually build several
components, so the ability to track metadata for parts of the build is also
included.

A metadata section may look like:
```
[metadata@my-product]
name=my-product
version=1.2.5
description=A product that delivers widgets to web developers
about=The widgets contained in 'my-product' allow developers to do fancy
    cool and neat-o things with their web pages.
 .
 There is no need for this library if you aren't using JavaScript
depends=npm (>= 3), javascript-caffine (> 2)
suggests=javascript-tools (== 2.4.3)
packager=My Product Co, Ltd. <my-product@myproduct.co.uk>
copyrights=my-product-copyright
keywords=widgets javascript node npm
#classifiers are python trove styled classifiers
# see: https://pypi.python.org/pypi?%3Aaction=list_classifiers
#These will be used to interpret intent of the package based on the packaging
target
classifiers=
   Development Status :: 4 - Beta
   Intended Audience :: Developers
   Topic :: Software Development :: Widget Sets
   Topic :: Internet :: WWW/HTTP :: Dynamic Content
   Programming Language :: JavaScript
   License :: OSI Approved :: MIT License

[copyright@my-product-copyright]
#Copyright license information follows https://www.debian.org/doc/packaging-
manuals/copyright-format/1.0/#license-specification
#Expat is a basic MIT license (there are many versions of the MIT license)
license=Expat
holder=My Product Co, Ltd. <copyright@myproduct.co.uk>
years=2010,2014-2015
disclaimer=All rights reserved as specified by the license
This is an example of a fairly well developed and comprehensive metadata
section.  Some projects may have several differing attributions which may all
be called out in the "copyrights" key in the metadata, referring to several
different copyrights and licenses associated with the specific attributions.
The minimum required is a project name and a version.  Then, of course, the
metadata can be built up over time as the product becomes more sophisticated
and closer to a release point.
An example of a simple metadata definition might look like:

[metadata@my-product]
name=my-product
version=0.0.0
```

The version is required to follow the "semantic versioning" standard, with a
major.minor.patch level styled version.  Other fields may be added to the
versioning information using a "versioning" section.
The metadata is intended to encapsulate a "best-of-class" definition based on
various popular packaging and delivery standards.
The most comprehensive resource for defining metadata for your project is
found in the module documentation for metadata:  csmake --list-type=metadata

## File Tracking in csmake
File tracking can be a significant help to anyone building.  If it's done
well, it's easy to modify your project by adding or deleting files and have
the build work without making changes to the build specification.  Some tools
have some implicit and explicit file tracking.  In make, for example, you can
define rules where the name of the rule is literally the extension of the file
and the output of the step - which may feed to another rule, and so on.
In csmake, the file tracking is orthogonal to the rest of the build
specification to ensure specifications remain completely specified and the
file tracking is easy to use or not use as needed/desired.

To achieve this orthogonality, file-tracking keys may be added to any section
that may be completely ignored by the module definition for that section.  For
example:
```
[Shell@my-file-generator]
**yields-files=<my-lib (text:placeholder)> touched.txt
command=touch %(RESULTS)s/touched.txt

[CompileCxx@my-cpp-builder]
**maps=<(cpp)> -(1-1)-> <(elf-relocatable)> obj/{~~filename~~}.o
flags=-wall -O3

[LinkStaticLib@my-linker]
**maps=<my-lib (elf-relocatable)> -(*-1)-> <(elf-lib)> libmylib.a
    && <my-other-lib (elf-relocatable)> -(*-1)-> <(elf-lib)> libmyotherlib.a
flags= -L%(SPECIAL_LIB_PATH)s

[command@do-compilations]
**files=
   <my-lib (cpp:library)> *.cpp,
   <my-other-lib (cpp:library)> other/*.cpp
0000=my-file-generator, my-cpp-builder, my-linker
```

The syntax is a bit cryptic - but essentially what the specification marks out
is a way to process two libraries with the same steps.  If the CompleCxx and
LinkStaticLib modules utilize the file tracking, then this specification would
build two libraries based on the *.cpp contents of the current working
directory and the "other" directory respectively.

Files in the file tracker have a type and a name, like <my-lib (cpp:library)>
*.cpp for example.

The file's type is a 3-axis type system designed to allow for representing
different aspects of the file:
```
< group-id ( file type : intent ) >
```
    - group-id:
       a bucket that any file can be added to.  These buckets
       understand history, and will identify only the final results when only the
       bucket is called out (more on this below)
    - file type:
       the literal type of the file - it is encouraged, but not
       required that this is the most specific mime type that describes the file
    - intent:
       is a way to annotate what the intended purpose for the file is in
       the build

Each of these axes are useful in different parts of the build, depending on
the purpose of a particular section and the whole build specification.

As you can see from the example, in mappings, only partial types need to be
used.  In the CompileCxx section, we see that we map anything that is a
literal file type of "cpp" to an "elf-relocatable" type.  The unspecified
parts on the right of the mapping are ignored when looking up the files and
when parts of the type are unspecified on the left, the resulting file will
inherit that part of the type from the left.  Again, for the CompileCxx step
this means that the .o's will maintain their group-id.  So, when the .o's get
to the LinkStaticLib step, they will be appropriately linked into the two
separate libraries.

As you can also see from the example, there are three different file tracking
statements you can add to a step: **files, **yields-files, **maps

    - **files:
          a way to tell the build specification that files exist (i.e.,
          are source files) and what type they should be given
    - **yields-files:
          a way to tell the build specification that a section
          will produce (or clean, etc) files with the specified type
    - **maps:
          defines how a section will map files from one type or
          file pattern to another - mappings can be one of 1-1, *-1, 1-*, or *-*  and,
          as demonstrated, multiple mappings can be defined using the ever popular "and"
          operator (&&)

To leave parts of the type out for the mappings, the proper separators need to
be present as things are left out from the left part of the type, for
example \<my-group\> would just be a group, which would only be the last results
available in the group (remember, groups maintain history).  <(text)> would
denote any file designated as a "text" type file.  <(:man-page)> would denote
(notice the colon to the left of "man-page") a specific purpose for the file
(like the purpose of the files we're mapping must be for a manpage, regardless
of what format or group the file is in).  <(text:man-page)> would denote a
text file that has the purpose of being a man-page (maybe not the best
choice...) from any group being tracked.

### (next parts to add)
    Examples
    Basic workflow/theory of operation
    Hitchhiker's guide to writing csmakefiles
    Module Developer's Guide

<sub>This material is under the GPL v3 license:

<sub>(c) Copyright 2017 Hewlett Packard Enterprise Development LP

<sub>This program is free software: you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation, either version 3 of the License, or (at your
option) any later version.

<sub>This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
Public License for more details.

<sub>You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
