PAPER := chi-2027-ja-review
FIGURE_NAMES := scenario-to-value detection-mechanism evaluation-protocol
SVG_FIGURES := $(addprefix figures/svg/,$(addsuffix .svg,$(FIGURE_NAMES)))
PDF_FIGURES := $(addprefix figures/pdf/,$(addsuffix .pdf,$(FIGURE_NAMES)))

.PHONY: all clean figures

all: output/pdf/$(PAPER).pdf

figures: $(PDF_FIGURES)

$(SVG_FIGURES): scripts/export-figures.mjs $(addprefix figures/src/,$(addsuffix .html,$(FIGURE_NAMES)))
	node scripts/export-figures.mjs

figures/pdf/%.pdf: figures/svg/%.svg
	mkdir -p figures/pdf
	rsvg-convert --format=pdf --output=$@.tmp $<
	gs -q -dBATCH -dNOPAUSE -sDEVICE=pdfwrite -dCompatibilityLevel=1.5 -sOutputFile=$@ $@.tmp
	rm -f $@.tmp

output/pdf/$(PAPER).pdf: main-ja.tex references.bib latexmkrc $(PDF_FIGURES)
	mkdir -p output/pdf build/texmf-var
	TEXMFVAR=$(CURDIR)/build/texmf-var TEXMFCACHE=$(CURDIR)/build/texmf-var latexmk -r latexmkrc main-ja.tex
	cp build/main-ja.pdf $@

clean:
	TEXMFVAR=$(CURDIR)/build/texmf-var TEXMFCACHE=$(CURDIR)/build/texmf-var latexmk -r latexmkrc -C main-ja.tex
	rm -f output/pdf/$(PAPER).pdf
	rm -f $(SVG_FIGURES) $(PDF_FIGURES)
