JAPANESE_PAPER := chi-2027-ja-review
ENGLISH_PAPER := chi-2027-en-review
FIGURE_NAMES := scenario-to-value detection-mechanism evaluation-protocol scenario-to-value-en detection-mechanism-en evaluation-protocol-en
SVG_FIGURES := $(addprefix figures/svg/,$(addsuffix .svg,$(FIGURE_NAMES)))
PDF_FIGURES := $(addprefix figures/pdf/,$(addsuffix .pdf,$(FIGURE_NAMES)))

.PHONY: all clean figures

all: output/pdf/$(JAPANESE_PAPER).pdf output/pdf/$(ENGLISH_PAPER).pdf

figures: $(PDF_FIGURES)

$(SVG_FIGURES): scripts/export-figures.mjs $(addprefix figures/src/,$(addsuffix .html,$(FIGURE_NAMES)))
	node scripts/export-figures.mjs

figures/pdf/%.pdf: figures/svg/%.svg
	mkdir -p figures/pdf
	rsvg-convert --format=pdf --output=$@.tmp $<
	gs -q -dBATCH -dNOPAUSE -sDEVICE=pdfwrite -dCompatibilityLevel=1.5 -sOutputFile=$@ $@.tmp
	rm -f $@.tmp

output/pdf/$(JAPANESE_PAPER).pdf: main-ja.tex references.bib latexmkrc figures/pdf/scenario-to-value.pdf figures/pdf/detection-mechanism.pdf figures/pdf/evaluation-protocol.pdf
	mkdir -p output/pdf build/texmf-var
	TEXMFVAR=$(CURDIR)/build/texmf-var TEXMFCACHE=$(CURDIR)/build/texmf-var latexmk -r latexmkrc main-ja.tex
	cp build/main-ja.pdf $@

output/pdf/$(ENGLISH_PAPER).pdf: main-en.tex references.bib latexmkrc figures/pdf/scenario-to-value-en.pdf figures/pdf/detection-mechanism-en.pdf figures/pdf/evaluation-protocol-en.pdf
	mkdir -p output/pdf build/texmf-var
	TEXMFVAR=$(CURDIR)/build/texmf-var TEXMFCACHE=$(CURDIR)/build/texmf-var latexmk -r latexmkrc main-en.tex
	cp build/main-en.pdf $@

clean:
	TEXMFVAR=$(CURDIR)/build/texmf-var TEXMFCACHE=$(CURDIR)/build/texmf-var latexmk -r latexmkrc -C main-ja.tex
	TEXMFVAR=$(CURDIR)/build/texmf-var TEXMFCACHE=$(CURDIR)/build/texmf-var latexmk -r latexmkrc -C main-en.tex
	rm -f output/pdf/$(JAPANESE_PAPER).pdf output/pdf/$(ENGLISH_PAPER).pdf
	rm -f $(SVG_FIGURES) $(PDF_FIGURES)
