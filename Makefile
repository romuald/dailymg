# Directory where source resides
SRCDIR := src

# Main package name
PACKAGE := dailymg

# Output executable zip file
TARGET := ${PACKAGE}

# root __main__.py file that will be executed
MAIN    := "import ${PACKAGE}; ${PACKAGE}.main()"
SHEBANG := "\#!/usr/bin/env python"

# Temporary files
TMPDIR  := $(shell mktemp -d temp.XXXXXXX)
TMPZIP  := ${TMPDIR}/archive.zip # zip tool needs a .zip extension
TMPMAIN := ${TMPDIR}/__main__.py

default: zip

clean:
	find ${SRCDIR} -name '*.py[co]' -print0 | xargs -0 rm -f

zip: clean
	cd ${SRCDIR} && zip -r -9 --exclude=*.egg-info* ../${TMPZIP} *
	echo ${MAIN} > ${TMPMAIN}
	zip -j ${TMPZIP} ${TMPMAIN}

	echo ${SHEBANG} | cat - ${TMPZIP} > ${TARGET}
	rm -r ${TMPDIR}
	chmod +x ${TARGET}
