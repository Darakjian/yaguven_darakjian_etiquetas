"""The company wordmark "DARAKJIAN", pre-rasterized to ZPL.

Converted ahead of time so printing depends on neither PIL nor a read of res.company.
Regenerate it if the logo changes: pull the PNG from `res.company.logo` and compose it
over a WHITE background (it is RGBA, and a thermal printer cannot print transparency).

HOW THE WORDMARK IS ISOLATED (this took two attempts): the "JEWELERS" subtitle canNOT be
separated by cutting at a fixed height, because it OVERLAPS the wordmark vertically -- in
the 640x118 PNG the wordmark occupies y=12..93 and the subtitle y=85..105. Cutting by
percentage eats the descender of the "J" and the mark comes out clipped at the bottom.
Nor is it enough to whiten "from row N downward" on the right: that band still holds the
last letters of the wordmark. The criterion that works:
  1. find the rows carrying ink ONLY on the right -> that is where the subtitle lives
     alone (y=94..105), and that gives the x where it starts (x=438);
  2. whiten the rectangle x>=438, y>=85 -- 85 being where the subtitle starts to overlap
     the descender of the J;
  3. only then take the bbox -> the wordmark isolated at 619x82.

The subtitle is dropped because at the height it would occupy on this tag it lands at
~3 dots and is unreadable. That is the printer's DPI (203) talking, not the resolution of
the file (the logo on darakjian.com is the same 640x118 PNG).

Dimensions: 100x13 dots @203dpi. They used to be 150x19, back when the wordmark took a
whole line of its own at the bottom right; with the banded layout it moved up to the top
band, beside the SKU and the price, and it stays legible at that size.
"""

LOGO_W = 100
LOGO_H = 13
LOGO_ZPL = "^GFA,169,169,13,7F00C07F00201C70E70180E06061C0C06180701840C301C070606061E06180701880C303C078606063606180D81900C302E05C606062307700981F00C306604E606063F06301FC1D80C307F0476060641861010C18C0C30C3043A060C41861830618E0C3083041E0618C1C60E2071870C31818C0E0761C0C7036071C1CC7181CC0600000000000000000C0000000000000000000000000800000000000000000000000010000000000"
