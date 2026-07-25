"""Wordmark "DARAKJIAN" del logo de la compania, ya rasterizado a ZPL.

Pre-convertido para no depender de PIL ni de leer res.company en cada impresion.
Regenerar si cambia el logo: bajar el PNG de `res.company.logo` y componerlo
sobre fondo BLANCO (es RGBA y la termica no imprime transparencia).

COMO SE AISLA EL WORDMARK (lo que costo dos intentos): el subtitulo "JEWELERS"
NO se separa cortando a una altura fija, porque **se solapa verticalmente** con
el wordmark — aca el wordmark ocupa y=12..93 y el subtitulo y=85..105. Cortar
por porcentaje se come el descendente de la "J" y la marca sale partida abajo.
Tampoco alcanza con blanquear "de tal fila para abajo" a la derecha: esa franja
todavia contiene las letras finales del wordmark. El criterio correcto:
  1. filas donde hay tinta SOLO a la derecha -> ahi vive el subtitulo puro;
  2. de ahi se saca la x donde arranca el subtitulo;
  3. subir desde esa banda mientras la zona derecha siga teniendo tinta -> eso
     delimita exactamente la contaminacion que se solapa con el wordmark;
  4. blanquear solo ese rectangulo y recien entonces sacar el bbox.

Se descarta el subtitulo porque a la altura que entra en esta etiqueta cae a
~3 dots y es ilegible: es el DPI de la impresora (203), no la resolucion del
archivo (el logo de darakjian.com es el mismo PNG de 640x118).

Medidas: 150x19 dots @203dpi.
"""

LOGO_W = 150
LOGO_H = 19
LOGO_ZPL = "^GFA,361,361,19,1FF8003003FF0001C00F87C1F3F003003C01E00F1F007801C3C001C0070700E1E007801E00C00E03807801C0E003E0070600E0E007801F00C00E01C0FC01C0E003E0070C00E0E00FC01F80C00E01E0DC01C0E006F0071800E0E00DC01BC0C00E00E18E01C1E00670077000E0E019E019E0C00E00E18E01E7800C7807F800E0E018E018F0C00E00E38F01FF800C3807B800E0E030F01878C00E00E3FF01C3801FFC071C00E0E03FF0183CC00E01E60381C1C0181C071C00E0E06078181EC00E01C60381C1C0301C070E00E0E06038180FC00E038C03C1C0E0300E070700E0E0C0381807C00E0F0C01C1C078600F070380E0E0C01C1803C01FFC3E03F3E01FF00F8F81F0E1F3E03F3C01C0000000000000020000000000C0000000000000000000000000000000000000C0000000000000000000000000000000000001800000000000000000000000000000000000030000000000000000000000000000000000000200000000000000"
