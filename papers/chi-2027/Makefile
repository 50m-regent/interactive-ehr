PAPER := chi-2027-ja-review

.PHONY: all clean

all: output/pdf/$(PAPER).pdf

output/pdf/$(PAPER).pdf: main-ja.tex references.bib latexmkrc
	mkdir -p output/pdf build/texmf-var
	TEXMFVAR=$(CURDIR)/build/texmf-var TEXMFCACHE=$(CURDIR)/build/texmf-var latexmk -r latexmkrc main-ja.tex
	cp build/main-ja.pdf $@

clean:
	TEXMFVAR=$(CURDIR)/build/texmf-var TEXMFCACHE=$(CURDIR)/build/texmf-var latexmk -r latexmkrc -C main-ja.tex
	rm -f output/pdf/$(PAPER).pdf
