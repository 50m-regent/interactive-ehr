PAPER := Hirata_Ren

.PHONY: all clean

all: output/pdf/$(PAPER).pdf

output/pdf/$(PAPER).pdf: main.tex references.bib latexmkrc
	mkdir -p output/pdf
	latexmk main.tex
	cp build/main.pdf $@

clean:
	latexmk -C main.tex
	rm -f output/pdf/$(PAPER).pdf
