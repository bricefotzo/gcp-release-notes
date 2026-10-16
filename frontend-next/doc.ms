Bloc 1, extractload (le nœud central)
Q1. Qui porte extractload aujourd'hui, même en intérim ? Et quelle politique assumes-tu : gel fonctionnel total (correctifs de sécurité seulement), ou maintenance minimale sur incidents prod ?
Aujourd'hui extractload est orphelin. L'équipe naturelle qui devrait s'en occuper ou du moins qu'on peut contacter est dataforge néamoins. par contre on peut tous y apporter des évolutions mais comme j'ai dit à éviter si ce n'est pas critique et si c'est faisable via K=GKE Argo Workflows templates
Q2. rclone vit-il techniquement dans extractload (un extracteur parmi d'autres) ou uniquement dans les templates Argo ? Et l'« Emergency SFTP exception » (extractload + rclone pour du SFTP urgent) : elle existe réellement et tu veux la garder comme dérogation encadrée, ou c'est un artefact d'agent à supprimer pour que le message reste net ?
rclone est simplement une techno qu'on utilise via l'image docker à différents endroits. on l'utilise bien pour les pipelines GKA Argo workflows qui font bouger des fichiers, c'est le no brainer. Par contre on l'a aussi intégré comme extractor dipsonible dans extracload. ça permet de faire du sftp cas(rapide, usernam password, fichier plat) proprement avec la syntaxe et le fonctionnement connu d'extractload. ce mode là n'est pas déprécié. ce mode n'est pas un cas Temporaire/Emergency. oui à faire en cas d'urgence ou du moins quand il n'y a pas le temps de développer un workflow si un aussi simple n'en existe pas
Q3. Quels SGBD sont réellement en prod via extractload ? J'ai trois listes différentes selon les pages (oracle/sqlserver/databricks +/- mysql/postgresql). Lesquels comptent vraiment, lesquels sont théoriques ?
oracle/sqlserver/databricks/mysql/postgresql

Bloc 2, les chiffres
Q4. Le rapport 867 sources pour 89 repos d'ingestion : c'est bien N fichiers sourceconf.yaml par repo ? Un ordre de grandeur (genre « ~10 sources par repo en moyenne ») me suffit pour écrire la phrase qui lève l'ambiguïté.
Je ne sais pas, il fadra refaie le compte. c'est très disparate d'un repo à l'autre.
Q5. Les 303 (35 % de 867) sont bien des sources et non des pipelines ? Et c'est bien ce volume-là qui constitue la cible de migration SFTP+API, ou le périmètre réel diffère ?
des sourceconf.yaml permette de configurer la source du pipeline qui est auto généré via dag generator et qui utilise en plus un tableconf pour la configuration de la table
Q6. Ces chiffres (867, 287, répartitions) datent de quand, et viennent-ils d'une extraction réelle (sourceconf + .gitlab-ci.yml) ou d'une estimation ? Je veux savoir si j'affiche une date de fraîcheur et à quel niveau de confiance.
Ils datent d'hier, mais récoltés par un agents, je ne sais pas trop, pas besoin d'en faire trop. tu peux rajouter effectivement comme date de collecte le 09/07
Bloc 3, Genedata / OMICs / patterns
Q7. Genedata (screener_assays) : tranché comment ? Option A, on le tue et il devient une simple config d'apis-extractor (aligné sur 05/06) ; option B, c'est une dérogation assumée avec sa justification. Pas les deux.
tu vas trop dans le détail. je ne comprends, où est-ce situé ça? dans les cas d'exemple?
Q8. L'ingestion OMICs en wget/bash : oubli (donc à ajouter aux cibles de migration comme le reste du shadow IT) ou dérogation légitime (HPC, volumétrie TB) à documenter comme telle ?
les ingestions omics sont particulières et donc bénéfient d'une dérogation qui n'en est pas vaiment une car l'idée est quand m^ême qu'ils construisent des briques réutilisables plus tard pour des besoins qui ressembleront aux leurs
Q9. Combien de patterns de contrat officiels vises-tu, et SAP/azure-toolbox a-t-il droit à son propre contrat dans 07 ? Veux-tu que je crée une correspondance explicite entre les chemins A-I de 01 et les patterns 1-8 de 07, ou ce sont deux grilles volontairement distinctes ?
Non tu peux virer SAP/azure-toolbox. je n'ai pas de chiffres en tête. Cette documentation est une v0 donc aide moi aussi à élaguer pour éviter qu'on s'y perde. Trop de documents peut tuer finalement le message.
Bloc 4, contrats de données
Q10. max_null_percentage : l'unité est une fraction (0 à 1) ou un pourcentage (0 à 100) ? Et le 1.0 sur response_rate (marqué required: true) dans le contrat Databricks, c'est une erreur d'agent ou c'est intentionnel ?
c'est une erreur ou du moins un niveau de détail encore trop accentué qui nuit à la finalité du message
Q11. Comportement standard quand un fichier échoue la validation de contrat : rejet, mise en quarantaine, ou simple alerte avec chargement quand même ? Ça manque et c'est structurant.
concernant les tout ce qui est GxP et les comportements à avoir, se rapprocher des équipes qualité notamment Pascal ROGER
Bloc 5, GxP
Q12. Qui est ton référent qualité/GxP pour valider les formulations avant publication ? (Je requalifie les sur-affirmations, mais la validation finale lui revient.)
Pascal ROGER. MAIS PAS SUR de comprendre pour valider les formulations de quoi? si tu parles de formulation de médicaments, nous ne faisons pas du tout ça, et une fois de plus ça va trop loin et hors du scope s'il y a eu ces mentions dans la doc par les agents
Q13. Es-tu d'accord pour remplacer « immediate GxP compliance » par une formule du type « contribue à la conformité, sous réserve de la qualification et de la traçabilité requises » ? Et existe-t-il une procédure ou un référentiel interne Servier à citer en appui plutôt que de laisser la phrase seule ?
je ne sais pas, trop loin une fois de plus
Bloc 6, action et structure
Q14. Pour les 303 sources à migrer : as-tu déjà les lots, les équipes porteuses et des trimestres cibles, ou je pose une trame avec des placeholders À définir que tu rempliras ?
non trop loin, je n'ai pas encore décidé de migrer des sources. C'est un luxe qu'on ne peut pas se permettre aujourd'hui donc si c'est une des actions ou recommendations proposées par les agents suppriment là, aujourd'hui je suis sur le pragmatisme. c'est à dire pour les nouveau on applique les règles pour les anciens on fera si nécesssaire des migrations dans un temps dédié et voulu si possible. mais le plus important c'est présent et futur qui respectent les guidelines
Q15. ADR : existe-t-il un template Servier officiel à réutiliser, ou je te propose un format léger (contexte, décision, alternatives, conséquences) ?
Non pas vraiment mais pareil t'attarde pas dessu, j'ai un collègue qui a proposé quelque chose dessus je vais regarder ça
Q16. Valides-tu la restructuration Diátaxis (4 sections : tutoriels / how-to / référence / explication) et le fait de sortir 06 (restitution) et 08 (pilote) vers un espace « adoption / programme » hors de l'arbre de référence ?
tutoriels et how ne sont pas pareil? mais sinon ok avec cette restructuration
Q17. Ton catalog.yaml par repo comme source unique de vérité pour les chiffres : cohérent avec l'extension Gemini que tu construis ? Si oui, je conçois la doc pour qu'elle affiche un rendu de ces chiffres plutôt que de les coder en dur, ce qui supprime mécaniquement les divergences.
supprime cette histoire de catalog.yaml qui n'est utilisée par personne aujourd'hui. tu peux me garder une page shadow pour moi afin que je puisse faire des tests et voir si c'est pertinent. si après tests ça l'est je l'introduirait, mais aujourd'hui n'en parle pas. je suis plutôt focus extension
Q18. On retire l'attribution « initially built by Facundo » (rôle neutre ou rien), ou tu tiens à créditer la personne ?
oui