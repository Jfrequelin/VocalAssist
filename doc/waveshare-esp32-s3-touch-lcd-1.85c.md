# Waveshare ESP32-S3-Touch-LCD-1.85C - Notes d'integration

## Source

- Wiki officiel: https://docs.waveshare.com/ESP32-S3-Touch-LCD-1.85C

## Carte cible retenue

- Variante cible: ESP32-S3-Touch-LCD-1.85C-BOX-EN
- Usage projet: satellite edge avec capture audio, wake word local, envoi backend, restitution audio et interface visuelle locale

## Capacites materielle confirmees

- ESP32-S3 double coeur Xtensa LX7 jusqu'a 240 MHz
- Wi-Fi 2.4 GHz et Bluetooth LE 5
- 16 MB de Flash
- 8 MB de PSRAM
- Ecran LCD rond 1.85" en 360x360, 262K couleurs
- Tactile capacitif via I2C avec interruption
- Codec audio embarque
- Microphone embarque
- RTC materielle
- Slot carte TF
- Gestion charge batterie Li-ion 3.7 V
- UART, I2C et header GPIO exposes

## Compatibilite de versions

- Le wiki indique que la V1 est arretee et remplacee par la V2 a partir du 30 janvier 2026.
- La V2 est a privilegier pour le projet.

## Differences importantes V1 / V2

- V1:
  - PCM5101APWR pour le decodeur audio
  - pas d'encodeur audio dedie
  - microphone numerique MEMS
  - pas d'annulation d'echo
- V2:
  - ES8311 pour le decodeur audio
  - ES7210 pour l'encodeur audio
  - microphones analogiques doubles
  - circuit d'annulation d'echo
  - meilleur support de la capture et de la lecture audio

## Consequences pour le systeme edge

- L'assistant physique possede bien un ecran: le logiciel edge doit donc prevoir une abstraction d'affichage.
- Le tactile permet d'envisager des commandes locales simples en plus du bouton physique.
- La V2 est nettement plus adaptee au cas d'usage vocal que la V1.
- Le mode batterie, la RTC et la gestion d'alimentation rendent possible un mode veille/reveil plus realiste.

## Fonctionnalites accessibles avec ce hardware

### Accessibles materiellement

- affichage local d'etat et de contenu sur ecran rond 360x360
- interaction tactile simple pour commandes locales, menus ou confirmations
- capture audio locale via microphone(s) embarque(s)
- restitution audio locale via haut-parleur de la speaker box
- connectivite Wi-Fi pour dialogue avec le serveur local
- BLE pour usages secondaires de provisionnement ou couplage futur
- persistance/stockage auxiliaire via carte TF
- horodatage local et fonctions temporelles via RTC
- fonctionnement sur batterie Li-ion avec recharge integree

### Accessibles mais non encore exploitees dans ce depot

- interface graphique ecran complete
- exploitation du tactile dans le flux edge
- gestion avancee batterie/veille/reveil
- usage RTC pour alarmes, reprise ou synchronisation locale
- usage TF pour logs, buffers ou cache local

### Deja couvertes ou simulees dans le depot actuel

- wake word local minimal
- VAD heuristique minimale
- envoi audio edge vers backend
- restitution TTS locale simulee
- etats appareil via LED, mute et bouton
- mode degrade et reprise apres indisponibilite backend

## Contraintes d'integration a respecter

- Le bus I2C expose sur GPIO10/GPIO11 est reserve aux composants embarques et aux peripheriques I2C externes; le wiki indique qu'il ne doit pas etre remappe comme GPIO generique.
- GPIO19/GPIO20 sont utilises pour l'USB; si on les reutilise autrement, il faut repasser en mode download pour flasher.
- La documentation constructeur semble evolutive: il faut figer une variante materielle (V2 idealement) avant d'ecrire le firmware final.

## Interfaces utiles pour le projet

- I2C:
  - SCL sur GPIO10
  - SDA sur GPIO11
- UART:
  - TXD sur GPIO43
  - RXD sur GPIO44
- USB:
  - DN sur GPIO19
  - DP sur GPIO20

## Impact sur la roadmap logicielle

- A court terme dans ce depot Python:
  - ajouter une abstraction ScreenController pour afficher les etats idle/listening/sending/speaking/error
  - conserver l'abstraction EdgeDeviceController pour LED/mute/bouton
  - preparer la separation entre comportement simule Python et futur firmware ESP-IDF/Arduino
- A moyen terme hors de ce depot:
  - firmware edge reel avec pilote ecran/tactile
  - integration audio adaptee a la revision materielle retenue
  - validation sur batterie, reseau degrade et cycle de veille

## Environnements de developpement recommandes par le wiki

- Arduino IDE pour prototypage rapide
- ESP-IDF pour integration plus fine et produit edge complexe

Pour ce projet, ESP-IDF est le choix le plus coherent pour le firmware cible, car il donne un meilleur controle sur l'audio, l'affichage, la connectivite et la gestion d'energie.