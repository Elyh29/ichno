import bpy

OP = "Operator"
FR = [
    ("*", "Objects", "Objets"), ("*", "Visible", "Visibles"), ("*", "Objects visible in the viewport", "Objets visibles dans la vue 3D"),
    ("*", "Selected", "Sélection"), ("*", "Selected objects only", "Objets sélectionnés seulement"),
    ("*", "Collection", "Collection"), ("*", "Objects of one collection", "Objets d'une collection"),
    ("*", "Front View", "Vue de face"), ("*", "Side of the model shown as the front view", "Côté du modèle montré en vue de face"),
    ("*", "Front (-Y)", "Avant (-Y)"), ("*", "Blender's front, numpad 1", "L'avant de Blender, pavé numérique 1"),
    ("*", "Back (+Y)", "Arrière (+Y)"), ("*", "Right (+X)", "Droite (+X)"), ("*", "Left (-X)", "Gauche (-X)"),
    ("*", "Top (+Z)", "Dessus (+Z)"), ("*", "Bottom (-Z)", "Dessous (-Z)"),
    ("*", "Size", "Format"), ("*", "Landscape", "Paysage"),
    ("*", "Projection", "Projection"), ("*", "European (First Angle)", "Européenne (premier dièdre)"),
    ("*", "American (Third Angle)", "Américaine (troisième dièdre)"),
    ("*", "ISO E, used in Europe and most of the world: left view on the right of the front view, top view below",
     "ISO E, utilisée en Europe et presque partout : vue de gauche à droite de la face, vue de dessus en dessous"),
    ("*", "ISO A, used in the USA and Canada: right view on the right of the front view, top view above",
     "ISO A, utilisée aux États-Unis et au Canada : vue de droite à droite de la face, vue de dessus au-dessus"),
    ("*", "Units", "Unités"), ("*", "Millimeters", "Millimètres"), ("*", "Centimeters", "Centimètres"), ("*", "Meters", "Mètres"),
    ("*", "Inches", "Pouces"), ("*", "Inches and imperial scales", "Pouces et échelles impériales"),
    ("*", "Secondary Units", "Unités secondaires"), ("*", "None", "Aucune"),
    ("*", "Dual dimensioning: second value in brackets, e.g. 254.0 [10.00]", "Double cotation : seconde valeur entre crochets, ex. 254,0 [10.00]"),
    ("*", "Scale", "Échelle"), ("*", "Largest standard scale that fits the sheet", "Plus grande échelle normalisée qui tient sur la feuille"),
    ("*", "Full size", "Grandeur nature"),
    ("*", "Isometric view", "Vue isométrique"), ("*", "Hidden lines", "Traits cachés"),
    ("*", "Dashed hidden lines (slow on heavy models)", "Traits cachés en pointillés (lent sur les modèles lourds)"),
    ("*", "On Isometric View", "Sur la vue isométrique"),
    ("*", "Also draw hidden lines on the isometric view (usually cluttered)", "Traits cachés aussi sur la vue isométrique (souvent chargée)"),
    ("*", "Axes", "Axes"), ("*", "Small X, Y, Z axis triad next to each view title", "Petit trièdre X, Y, Z à côté du titre de chaque vue"),
    ("*", "Line weight", "Épaisseur des traits"), ("*", "Fine", "Fins"), ("*", "Normal", "Normaux"), ("*", "Bold", "Épais"),
    ("*", "Crease angle", "Angle des arêtes"), ("*", "Edges sharper than this are drawn", "Les arêtes plus vives que cet angle sont dessinées"),
    ("*", "Drawing Language", "Langue du plan"), ("*", "Language of the texts on the drawing", "Langue des textes du plan"),
    ("*", "Same as Blender's interface", "Comme l'interface de Blender"), ("*", "English", "Anglais"), ("*", "French", "Français"),
    ("*", "Title", "Titre"), ("*", "Project", "Projet"), ("*", "Drawing No.", "N° de plan"),
    ("*", "Drawing number, also the file name", "Numéro du plan, aussi nom du fichier"), ("*", "Company", "Société"),
    ("*", "Logo", "Logo"), ("*", "Image shown in the title block (PNG, JPEG…)", "Image affichée dans le cartouche (PNG, JPEG…)"),
    ("*", "Author", "Auteur"), ("*", "Revision", "Révision"),
    ("*", "Folder", "Dossier"), ("*", "Open PDF", "Ouvrir le PDF"), ("*", "Open the PDF when the plan is done", "Ouvrir le PDF quand le plan est prêt"),
    ("*", "Sheets by Collection", "Feuilles par collection"),
    ("*", "One sheet per group of collections, each with its name and scale",
     "Une feuille par groupe de collections, chacune avec son nom et son échelle"),
    ("*", "Name", "Nom"), ("*", "Sheet", "Feuille"),
    ("*", "View", "Vue"), ("*", "Top", "Dessus"), ("*", "Front", "Face"), ("*", "Side", "Côté"),
    ("*", "Reference", "Référence"), ("*", "Point of each object used as a station", "Point de chaque objet pris comme repère"),
    ("*", "Left Edge", "Bord gauche"), ("*", "Center", "Centre"), ("*", "Right Edge", "Bord droit"), ("*", "Origin", "Origine"),
    ("*", "Tolerance", "Tolérance"), ("*", "Positions", "Positions"),
    ("*", "Write each station's coordinate from the world origin under the chain",
     "Écrit sous la chaîne la coordonnée de chaque repère depuis l'origine du monde"),
    ("*", "Intervals that differ by less than this are merged into “n × pitch” (model imprecision)",
     "Les intervalles qui diffèrent de moins que cela sont réunis en « n × pas » (imprécisions du modèle)"),
    ("*", "Chain Dimensions", "Cotes en chaîne"), (OP, "Add Chain", "Ajouter une chaîne"), (OP, "Remove Chain", "Retirer la chaîne"),
    ("*", "Add a chain dimension", "Ajoute une cote en chaîne"), ("*", "Remove the active chain dimension", "Retire la cote en chaîne active"),
    ("*", "Revisions", "Révisions"), ("*", "Custom Fields", "Champs libres"), ("*", "Remarks", "Remarques"),
    ("*", "Ownership", "Mention de propriété"), ("*", "Rev.", "Rév."), ("*", "Description", "Description"), ("*", "Date", "Date"),
    ("*", "Field", "Champ"), ("*", "Value", "Valeur"),
    ("*", "Text (Text Editor) written above the title block", "Texte (éditeur de texte) écrit au-dessus du cartouche"),
    ("*", "Ownership notice at the bottom of the title block, e.g. “This drawing is the property of … — all rights reserved”",
     "Mention en bas du cartouche, ex. « Ce dessin est la propriété de … — tous droits réservés »"),
    ("*", "Write the remarks in the Text Editor", "Écris les remarques dans l'éditeur de texte"),
    (OP, "Add", "Ajouter"), (OP, "Remove", "Retirer"), ("*", "Add a row", "Ajoute une ligne"), ("*", "Remove the active row", "Retire la ligne active"),
    ("*", "Coordinate Grid", "Grille de coordonnées"), ("*", "Mode", "Mode"), ("*", "Ruler", "Règle"), ("*", "Grid", "Grille"),
    ("*", "Graduations in world coordinates above and left of the views", "Graduations en coordonnées du monde au-dessus et à gauche des vues"),
    ("*", "Architect grid: axis lines with bubbles 1, 2, 3 and A, B, C", "Grille d'architecte : lignes d'axes avec bulles 1, 2, 3 et A, B, C"),
    ("*", "Step", "Pas"), ("*", "Spacing in drawing units; 0 = automatic (about 10 intervals)", "Écart dans l'unité du plan ; 0 = automatique (une dizaine d'intervalles)"),
    ("*", "Object whose location is the zero of the coordinates (world origin if empty)", "Objet dont la position est le zéro des coordonnées (origine du monde si vide)"),
    ("*", "Draw", "Dessiner"), ("*", "Draw the front view", "Dessine la vue de face"), ("*", "Draw the side view", "Dessine la vue de côté"),
    ("*", "Draw the top view", "Dessine la vue de dessus"), ("*", "No view selected (Views panel)", "Aucune vue choisie (panneau Vues)"),
    ("*", "Object Labels", "Étiquettes d'objets"), ("*", "Isometric", "Isométrique"), ("*", "Text", "Texte"), ("*", "Fast", "Rapide"),
    ("*", "About a third faster on heavy models: back faces ignored and no intersection lines (lines missing on open surfaces seen from behind and where two objects cross); for drafts",
     "Environ un tiers plus rapide sur les gros modèles : faces arrière ignorées et sans lignes d'intersection (traits en moins sur les surfaces ouvertes vues de dos et là où deux objets se traversent) ; pour les brouillons"), ("*", "Combine Equal Spacing", "Réunir les espacements égaux"),
    ("*", "Equal intervals in a row written once as “n × pitch = total”; off: every interval and every position dimensioned",
     "Intervalles égaux qui se suivent écrits une fois « n × pas = total » ; décoché : chaque intervalle et chaque position cotés"), ("*", "Own Views", "Vues propres"),
    ("*", "This sheet draws its own views instead of those of the Views panel", "Cette feuille dessine ses propres vues au lieu de celles du panneau Vues"),
    ("*", "no view selected", "aucune vue choisie"), ("*", "Legend", "Légende"), ("*", "Abbreviation", "Abréviation"), ("*", "Viewpoint", "Point de vue"),
    ("*", "Corner the isometric view is seen from", "Coin depuis lequel la vue isométrique est vue"),
    ("*", "Front and the side shown by the side view", "Face et côté montré par la vue de côté"), ("*", "Front Left", "Avant gauche"),
    ("*", "Front Right", "Avant droit"), ("*", "Back Left", "Arrière gauche"), ("*", "Back Right", "Arrière droit"),
    ("*", "Viewport", "Vue 3D"), ("*", "Same angle as the 3D Viewport (orthographic, from the view's direction)",
     "Même angle que la vue 3D (orthographique, selon la direction de la vue)"), ("*", "Hide .001 Suffix", "Masquer le suffixe .001"),
    ("*", "Write Frame instead of Frame.001", "Écrit Cadre au lieu de Cadre.001"), ("*", "Text Size", "Taille du texte"),
    ("*", "Height of the label text on the sheet (mm)", "Hauteur du texte des étiquettes sur la feuille (mm)"), ("*", "Object Name", "Nom de l'objet"),
    ("*", "Name of each object (a collection instance: its empty)", "Nom de chaque objet (une instance de collection : son vide)"),
    ("*", "Value of a custom property; objects without it are not labeled",
     "Valeur d'une propriété personnalisée ; les objets qui ne l'ont pas ne sont pas étiquetés"),
    ("*", "Bill of Materials", "Nomenclature"), ("*", "Count by", "Compter par"), ("*", "Base Name", "Nom de base"),
    ("*", "Objects named Seat, Seat.001… count as one row “Seat”", "Les objets Siège, Siège.001… comptent sur une ligne « Siège »"),
    ("*", "One row per collection", "Une ligne par collection"), ("*", "Custom Property", "Propriété personnalisée"),
    ("*", "One row per value of a custom property", "Une ligne par valeur d'une propriété personnalisée"), ("*", "Property", "Propriété"),
    ("*", "Custom property of the objects (Object Properties > Custom Properties)",
     "Propriété personnalisée des objets (Propriétés de l'objet > Propriétés personnalisées)"),
    ("*", "Views", "Vues"), ("*", "Title Block", "Cartouche"), ("*", "Output", "Sortie"), ("*", "Lines", "Traits"), ("*", "Annotations", "Annotations"),
    ("*", "Front, Side, Top", "Face, côté, dessus"), ("*", "Labels", "Étiquettes"), ("*", "Chains", "Chaînes"), ("*", "Grid", "Grille"),
    ("*", "BOM", "Nomenclature"),
    (OP, "Make Plan", "Dessiner le plan"), (OP, "Cancel", "Annuler"), (OP, "Open Last Plan", "Ouvrir le dernier plan"),
    (OP, "Add Sheet", "Ajouter une feuille"), (OP, "Remove Sheet", "Retirer la feuille"),
    (OP, "One Sheet per Collection", "Une feuille par collection"), (OP, "Add Collection", "Ajouter une collection"),
    (OP, "Remove Collection", "Retirer la collection"), (OP, "Move Sheet", "Déplacer la feuille"),
    ("*", "Move the active sheet up or down (order of the pages)", "Monte ou descend la feuille active (ordre des pages)"),
    ("*", "Draw the plan (PDF and SVG) in the background, without changing the scene",
     "Dessine le plan (PDF et SVG) en arrière-plan, sans modifier la scène"),
    ("*", "Stop the plan being drawn", "Arrête le plan en cours"), ("*", "Open the last plan", "Ouvre le dernier plan"),
    ("*", "Add a sheet", "Ajoute une feuille"), ("*", "Remove the active sheet", "Retire la feuille active"),
    ("*", "One sheet per top-level collection of the scene (replaces the list)",
     "Une feuille par collection principale de la scène (remplace la liste)"),
    ("*", "Add a collection to the active sheet", "Ajoute une collection à la feuille active"),
    ("*", "Remove the collection from the active sheet", "Retire la collection de la feuille active"),
    ("*", "The title becomes the generic name", "Le titre devient le nom générique"),
    ("*", "Collections of “{}”", "Collections de « {} »"), ("*", "Sub-collections of “{}” only", "Sous-collections de « {} » seulement"),
    ("*", "no collection", "aucune collection"), ("*", "collection outside “{}”", "collection hors de « {} »"),
    ("*", "nothing to draw (check Objects)", "rien à dessiner (vérifie Objets)"), ("*", "Sheet “{}”: {}", "Feuille « {} » : {}"),
    ("*", "Nothing to draw", "Rien à dessiner"), ("*", "Starting…", "Démarrage…"), ("*", "Cancelled", "Annulé"),
    ("*", "Blender stopped before the end (code {})", "Blender s'est arrêté avant la fin (code {})"), ("*", "log", "journal"),
    ("*", "Cannot write “{}” in {}", "Impossible d'écrire « {} » dans {}"),
    ("*", "“{}” is open in another program: saved as “{}”", "« {} » est ouvert dans un autre programme : enregistré sous « {} »"),
    ("*", "Error", "Erreur"), ("*", "{} sheet in {} s", "{} feuille en {} s"), ("*", "{} sheets in {} s", "{} feuilles en {} s"),
    ("*", "No collection with objects", "Aucune collection avec des objets"),
]
TRANSLATIONS = {"fr_FR": {(ctx, en): fr for ctx, en, fr in FR}}


def tr(key, *args):
    return bpy.app.translations.pgettext_iface(key).format(*args)


def rpt(key, *args):
    return bpy.app.translations.pgettext_rpt(key).format(*args)


def drawing_lang(choice):
    if choice in ("en", "fr"):
        return choice
    loc = bpy.app.translations.locale or ""
    return "fr" if loc.startswith("fr") and bpy.context.preferences.view.use_translate_interface else "en"


def register():
    bpy.app.translations.register(__package__, TRANSLATIONS)


def unregister():
    bpy.app.translations.unregister(__package__)
