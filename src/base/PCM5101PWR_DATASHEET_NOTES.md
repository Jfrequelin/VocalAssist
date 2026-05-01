# Texas Instruments PCM5101PWR - Notes d'integration

Source integree:
- TI datasheet PCM5100/PCM5101/PCM5102
- URL: https://files.waveshare.com/wiki/common/TexasInstruments-PCM5101PWR.pdf

Objectif:
- cadrer l'implementation audio playback cote base edge a partir des contraintes reelles du DAC.

## 1) Caracteristiques utiles au projet

- Type: DAC stereo audio DirectPath (sortie centree GND)
- Interface PCM serie jusqu'a 32-bit
- Frequence d'echantillonnage: 8 kHz a 384 kHz
- Formats supportes: I2S et Left-Justified (selection via pin FMT)
- Sortie pleine echelle: 2.1 VRMS (ground centered)
- Alimentation nominale de reference dans le datasheet: AVDD = CPVDD = DVDD = 3.3 V
- Package: TSSOP-20

## 2) Horloges et mode 3 fils I2S

- Port audio principal: LRCK, BCK, DIN (3-wire serial)
- Le composant peut fonctionner sans MCLK externe via PLL interne, en derivant SCK depuis BCK
- Le PLL interne s'active si BCK/LRCK sont valides et SCK absent pendant 16 periodes LRCK
- Le composant accepte des mots audio 16/24/32 bits

Implication implementation:
- prioriser une configuration I2S 3 fils stable dans `playback.py`
- monitorer validite LRCK/BCK (perte ou incoherence)
- fallback propre si horloges invalides

## 3) Gestion mute, erreurs d'horloge et pop-free

- Mute intelligent a deux niveaux (soft mute + analog mute)
- Detection de clock halt/error (SCK/BCK/LRCK) avec bascule stand-by / power-down selon condition
- Auto mute si donnees nulles prolongees (zero-data detect)
- Le composant est pense pour operation pop-free lors des changements d'etat/horloge

Implication implementation:
- appliquer rampes soft mute/unmute cote firmware au changement d'etat vocal
- stopper proprement les horloges I2S avant power-down
- reprendre playback uniquement apres revalidation clocks

## 4) Alimentation et protection

- Domaines d'alimentation identifies: DVDD, AVDD, CPVDD
- Negative charge pump integree (VNEG/CAPP/CAPM)
- UVP/Reset et modes de protection avec pin XSMT dans certains scenarii

Implication implementation:
- sequence d'init audio ordonnee: alimentation stable -> clocks -> stream
- en cas de brown-out/undervoltage: muter avant coupure audio
- journaliser les transitions power/mute pour debug

## 5) Qualite audio et latence

- Dynamic range de la famille: jusqu'a 112/106/100 dB (PCM5102/5101/5100)
- THD+N nominale de la famille: environ -93/-92/-90 dB a -1 dBFS
- Filtres interpolation avec mode latence normale ou faible latence

Implication implementation:
- exposer un profil playback standard vs low-latency
- valider jitter/performance en conditions Wi-Fi chargees
- conserver un buffer audio limite mais suffisant pour eviter les artefacts

## 6) Exigences derives pour src/base

- `playback.py`
  - config I2S explicite (format, largeur mot, frequence)
  - gestion soft mute/unmute et transitions d'etat
  - supervision clock halt et reprise
- `runtime.py`
  - orchestration etat speaking/muted/error coherente avec pipeline audio
- `resilience.py`
  - strategie de recovery audio si perte clock / perte alimentation / reset DAC

## 7) Checklist validation playback (PCM5101)

- [ ] Playback I2S fonctionnel en 16/24/32-bit
- [ ] Pas de pop audible sur start/stop/mute/unmute
- [ ] Recovery valide apres perte BCK/LRCK
- [ ] Latence de reprise compatible cible produit
- [ ] Logs exploitables sur transitions audio critiques
