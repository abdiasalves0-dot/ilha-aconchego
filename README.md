# 🌴 Ilha Aconchego

Um jogo de vida tranquila numa ilha, inspirado no estilo de *Animal Crossing*, feito com **Three.js** (jogo no navegador)
e **Blender** (modelagem 100% por script). Todo o visual é original no mesmo estilo; nenhum asset da Nintendo é usado.

## Como jogar

Requer [Node.js](https://nodejs.org) (só para baixar o Three.js) e Python (servidor local).

```bash
npm install
python -m http.server 8080
```

Abra http://localhost:8080 (no Windows, dê dois cliques em `jogar.bat`).

| Tecla | Ação |
|---|---|
| `W A S D` | andar (`Shift` corre) |
| `E` | interagir (conversar, colher, sacudir árvores, pescar, vender) |
| `Espaço` | rede de borboletas |
| `I` | bolso (inventário) |
| `C` | guarda-roupa |

## O que tem

- Ilha com mundo curvo, ciclo de dia e noite, céu, estrelas, nuvens, chão e grama procedurais
- Pós-processamento (oclusão de ambiente, contorno, bloom, gradação por horário) e resolução adaptativa
- Tela inicial, criação de personagem (pele, cabelo, olhos, roupas), inventário e guarda-roupa estilo ACNH
- Personagem com esqueleto articulado (joelhos/cotovelos) e caminhada por cinemática inversa
- Aldeões, frutas, flores, pesca, borboletas, loja, música gerada em tempo real

## Estrutura

```
index.html / style.css / src/main.js   o jogo
assets/models/                         modelos .glb (gerados no Blender)
assets/models/char2/                   personagem-base, roupas e cabelos (+ wardrobe2.json)
blender/                               scripts do Blender (modelagem, prévias, testes de pose)
.claude/skills/roupas-animal-crossing  guia para criar roupas/cabelos novos
```

## Regenerar os modelos (Blender 5.x)

```bash
blender -b -P blender/build_assets.py        # cenário, casas, árvores, aldeões
blender -b -P blender/build_char2.py         # personagem + roupas + cabelos (precisa de vendor_ref/base_blend/clean.blend)
```

`build_char2.py` parte de um `base.blend` fornecido pelo autor do projeto, que **não** está neste repositório
(`vendor_ref/` é ignorado). Veja `blender/clean_base_blend.py`.

## Licença dos assets

Os modelos em `assets/` foram gerados por scripts e são do projeto. Modelos de terceiros usados como referência
(Meshy, Macchiato) ficam fora do repositório por não terem licença clara.
