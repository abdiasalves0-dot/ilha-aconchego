---
name: roupas-animal-crossing
description: Cria roupas, calçados e penteados 3D no estilo Animal Crossing para o jogo Ilha Aconchego (Blender headless + three.js). Use quando o usuário pedir uma peça nova (camiseta, moletom, vestido, saia, calça, sapato, chapéu, cabelo), um novo padrão/estampa de tecido, uma cor de cabelo, ou quiser ajustar o guarda-roupa do personagem.
---

# Roupas e cabelos estilo Animal Crossing

O personagem é um **corpo-base chibi** (folha de turnaround do Meshy em `vendor_ref/chibi_base/`) + **peças separadas**,
cada uma num `.glb` em `assets/models/char/`. Todas as peças têm os mesmos pivôs
(`Root, Head, ArmL, ArmR, FootL, FootR`), então o jogo encaixa qualquer combinação (`buildAvatar` em `src/main.js`).

## Arquivos

| Arquivo | Função |
|---|---|
| `blender/char_lib.py` | Biblioteca: `load_base`, `improve_skin`, `shell` (roupa = casca do corpo), `lock` (mecha/tubo afilado), `export_character` (baixa os braços retos, separa as partes, exporta) |
| `blender/build_wardrobe.py` | Define TODAS as peças e penteados e gera `wardrobe.json` |
| `blender/preview_combo.py` | Renderiza visuais lado a lado para conferir |
| `assets/models/char/wardrobe.json` | Manifesto lido pelo jogo (id, slot, nome, arquivo, `full`, cores de cabelo) |

Slots: `top`, `bottom`, `shoes`, `hair`. Um `top` com `"full": true` (vestido) esconde o `bottom`.

## Técnica (pesquisada)

- **Roupa = casca do corpo**: duplicar as faces do corpo na região da peça, afastar da pele (offset ao longo da normal de um
  corpo *suavizado*), **Shrinkwrap "OUTSIDE"** contra o corpo real (a pele nunca atravessa), suavizar, cortes retos
  com `bisect` (barras, golas, mangas), **Solidify** (espessura) e **Subdivision**. Tudo isso já está em `cl.shell(...)`.
- **Peças que não seguem o corpo** (saias, capuz, sapatos, chapéus): primitivas simples e "gordinhas" (`skirt_cone`,
  esferas/cilindros de `ba.sphere`/`ba.cyl`). Forçar a parte com `force={"nome": "Root"}` para a saia não se dividir entre as pernas.
- **Cabelo = volumes lisos esculpidos**, não fios: calota (`hair_cap`, elipsoide cortado na linha do cabelo) + lóbulos
  (`lobe`) / mechas (`cl.lock`) → `sculpt()` funde com Voxel Remesh + Smooth, aplica UV esférica (textura de fios com
  faixa de brilho) e sombreamento por vértice. A cor é aplicada no jogo (`hairColors`), a textura é cinza clara.

## Regras de estilo ACNH

1. Silhueta simples, cantos arredondados, nada de dobras realistas. Barras e golas um pouco mais grossas (offset maior).
2. Tecido = cor chapada + trama sutil (`fabric("cotton"|"denim"|"knit"|"stripes"|"pleat")`). Estampas grandes e simples
   no peito, com UV planar (`planar_uv` + material de frente). Paleta pastel e saturada, sem preto puro.
3. Offsets típicos (fração da altura): camiseta 0.008, moletom 0.013, calça 0.009–0.01, barras/gola +0.006–0.007,
   bolsos/peitilhos 0.017–0.02. Espessura 0.004–0.006.
4. Calçados chunky: cabedal (esfera achatada) + sola clara + biqueira.
5. Nunca reutilizar o cabelo branco com chifres nem a roupa xadrez (pedido do usuário).

## Como adicionar uma peça

1. Em `build_wardrobe.py`, crie a peça na seção do slot e chame:
   ```python
   export_piece("top_regata", "top", "Regata Verde", tee("top_regata", "Regata Verde", "#7cc57a", sleeve=TH * 1.02))
   ```
   Ids começam com o slot (`top_`, `bottom_`, `shoes_`, `hair_`). Para penteados: `hair_style("hair_x", "Nome", builder)`
   onde `builder(m)` devolve `(lista_de_objetos, cortes)`.
2. Gere só essa peça (o manifesto é mesclado):
   ```bash
   "/c/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b -P blender/build_wardrobe.py -- top_regata
   ```
   Se mudar algo de `char_lib` que afete pivôs/braços (`ARM_*`, `X0`, `bend_arms`), gere **tudo** de novo (sem `--`),
   inclusive o `body`, senão as peças não encaixam.
3. Confira visualmente antes de levar ao jogo:
   ```bash
   "/c/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b -P blender/preview_combo.py -- "C:/Users/sambalele/animalcrossing/vendor_ref/wardrobe.png" "hair_curto:#7a4a2c,top_regata,bottom_short_jeans,shoes_tenis"
   ```
   e leia `vendor_ref/wardrobe_front.png` / `_34.png`. Procure: pele atravessando, pontas soltas, peça fora do lugar.
4. No jogo (`jogar.bat`, tecla **C**), a peça aparece sozinha na lista do slot.

## Armadilhas conhecidas

- Rodar scripts com `undo_steps = 0` (já feito em `load_base`); senão a memória estoura.
- `Solidify` com `use_even_offset` pode lançar vértices longe e explodir o Voxel Remesh. Deixe desligado.
- Prints dentro do Blender: use `flush=True` para ver onde travou.
- A malha do Meshy é ruidosa: nunca use as normais cruas dela para afastar roupas (use `body_proxy`).

## Corpo, pele, olhos e braços

- Braços no estilo ACNH: retos e abertos ~28° (`M["ARM_ANGLE"] = 62°` em `char_lib.measure`) e alongados
  (`ARM_STRETCH`, só o trecho ombro→punho; a mão não deforma). Mudou isso? Gere **todas** as peças de novo.
- `improve_skin` grava a pele no tom `SKIN_BASE` (#e8955c, o da referência) e gera `assets/textures/base_skin_mask.png`
  (R = pele, G = íris). No jogo, `skinMaterial()` multiplica a pele pelo tom escolhido e troca a cor da íris.
  Tons e cores de olho ficam em `SKIN_TONES` / `EYE_COLORS` (`src/main.js`).
- Blush: duas malhas `Blush*` (material `blush`) na cabeça do `body.glb`, ligadas/desligadas por `look.blush`.
- Tela de criação de personagem (`openCreator`): primeira tela de um jogo novo; abas Pele, Cabelo, Olhos, Bochechas, Roupa.
  Peças novas aparecem sozinhas lá, com ícone renderizado do próprio modelo.

## Pés e calçados

- O pé do Meshy vinha como uma bolota simétrica. `char_lib.reshape_feet` (chamado em `load_base`) remodela o pé como na
  referência: bico arredondado para a frente e calcanhar. Tudo que é feito a partir do corpo herda esse formato.
- Calçado = `shoe_volume`: cópia do **próprio pé** ampliada a partir do centro de cada pé, boca cortada reta, e
  `zmin` para o cabedal apoiar em cima da sola (sem brigar com ela). A sola é a base do mesmo pé, mais larga e mais alta.
  Não use casca + remesh para calçados (fica amassado) nem esferas (perde o formato do pé).
- Conferir de lado: `blender -b -P blender/preview_feet.py -- vendor_ref/feet.png "" "bottom_short_jeans,shoes_tenis"`.

## Calçados (versão final): sapato por loft

Esferas e cópias ampliadas do pé ficam como "bola achatada". O sapato do ACNH é comprido (~2x a largura), com bico baixo e
redondo levemente erguido, sola grossa de outra cor, calcanhar definido e boca no tornozelo. `build_wardrobe.shoes` usa
`loft(...)`: seções meia-superelipse com base plana ao longo do pé, com funções `wfun(t)`/`hfun(t)` (t=0 calcanhar, t=1 bico).
A altura tem pico na posição da perna (`tl`). Ajuste forma mexendo nessas funções e conferindo de lado com `preview_feet.py`.

## Esqueleto articulado (char2) e animação de andar

- O personagem atual vem de `build_char2.py` (corpo e roupas do `base.blend`). O esqueleto tem 12 ossos:
  `Root, Head, ArmL/R, ElbowL/R, FootL/R (quadril), KneeL/R, AnkleL/R`. Todas as peças são malhas "skinned" nos MESMOS ossos,
  com pesos calculados por posição em T-pose (`weights_at`), então corpo, roupa e cabelo deformam juntos, sem costuras.
- `src/main.js > animateRig`: pernas por cinemática inversa de 2 ossos (apoio: pé recua em linha reta; balanço: pé levanta e
  o joelho dobra), quique 2x por ciclo, quadril balançando, braços opostos com cotovelo, tudo em eixos do avatar (`setRot`/`setPos`).
- Conferir o desenho do passo sem abrir o jogo: `blender -b -P blender/walk_strip.py -- vendor_ref/walk_strip.png`.
  Testar deformação em poses extremas: `blender -b -P blender/preview_pose.py -- vendor_ref/pose.png "top_moletom:#fff" ...`.
- Mudou medidas de joelho/tornozelo (`KNEEZ`, `ANKLEZ`) ou a lista de ossos? Gere TODAS as peças de novo (sem `--`).
