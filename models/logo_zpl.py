"""Wordmark "DARAKJIAN" del logo de la compania, ya rasterizado a ZPL.

Se guarda pre-convertido para no depender de PIL ni de leer res.company en cada
impresion. Para regenerarlo si cambia el logo: bajar el PNG de `res.company.logo`,
componerlo sobre fondo BLANCO (la termica no imprime transparencia), recortar la
banda del wordmark separandola de "JEWELERS" y umbralizar a 1 bit.

Por que se descarta el subtitulo: a la altura que entra en esta etiqueta cae a
~3 dots y sale ilegible. No es un problema de resolucion del archivo — el logo
publicado en darakjian.com es el mismo de 640x118 — sino del DPI de la
impresora (203). El wordmark solo entra mas grande y se lee nitido.

Medidas: 150x15 dots @203dpi.
"""

LOGO_W = 150
LOGO_H = 15
LOGO_ZPL = "^GFA,285,285,19,1FF8003003FF0001C00F87C1F3F003003C01E00F1F007801C3C001C0070700E1E007801E00C00E03807801C0E003E0070600E0E007801F00C00E01C0FC01C0E003E0070C00E0E00FC01F80C00E01E0DC01C0E006F0071800E0E00DC01BC0C00E00E18E01C1E00670077000E0E019E019E0C00E00E18E01E7C00C7807F800E0E018E018F0C00E00E18F01FF800C3807B800E0E030F01878C00E00E3FF01C3801FF8071C00E0E03FF0183CC00E00E20781C1C0181C071C00E0E06070181EC00E01C60381C1C0301C070E00E0E06038180FC00E03C403C1C0E0300E070700E0E0C0381807C00E070C01C1C070600F070380E0E0C01C1803C01FFE1E03F1E03EF00F8F81F0E1E3C03E3C01C0000000000000070000000070C0000000000080"
