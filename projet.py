# importation des libraries ---------------------------------------------------------------------------------------------------------
import json ; import re ; import warnings ; import pandas as pd
from math import pi
from bokeh.plotting import figure, show
from pyproj import Proj, transform
from bokeh.models import HoverTool, ColumnDataSource, Panel, Legend, ColumnDataSource, Circle, Div, Tabs, RangeSlider, DataTable, TableColumn, TextInput, Button, CustomJS
from bokeh.tile_providers import get_provider, Vendors
from bokeh.palettes import Category20b
from bokeh.layouts import row, column, gridplot, widgetbox
from bokeh.models.widgets import DataTable, DateFormatter, TableColumn
from bokeh.io import show
from bokeh.transform import cumsum


# définition de fonctions ------------------------------------------------------------------------------------------------------------
pd.options.mode.chained_assignment = None # enlever les warnings de pandas
warnings.filterwarnings("ignore")

# fonction pour convertir les différentes formes de valeurs en type numérique
def convert_to_numeric(val):
    if re.match(r'^\d+$', str(val)):
        return int(val)
    elif re.match(r'^\d+\-\d+$', str(val)):
        # convertie en la moyenne des deux nombres si "3-4"
        return int(sum(map(int, str(val).split('-'))) / 2)
    elif re.match(r'^\d+$|^env\. \d+$|^\>\d+$|^\< \d+$', str(val)):
        return float(re.findall(r'\d+\.?\d*', str(val))[0])
    else:
        return None

# Chargement des données ------------------------------------------------------------------------------------------------------------

fp = open("Projet/observations-faunistiques-bretagne.json")
mondict = json.load(fp)
#print(mondict)
df = pd.DataFrame(mondict)
#print(df.columns)

# Traitement des données ------------------------------------------------------------------------------------------------------------

df['nombre'] = df['nombre'].apply(convert_to_numeric) 
df = df[df['nombre'].notna()] # traitement des valeurs manquantes

# Remplacer le "Z" par une chaîne vide dans la date
df['date'] = df['date'].str.replace('Z', '')
df['date'] = pd.to_datetime(df['date']) # format datetime
#print(df['date'])

# Supprimer les sous-categories d'oiseaux non renseignées
df = df[df["sous_categorie"] != "-"]
#print(df.groupby('sous_categorie').size())

# Comptage du nombre d'espèces par categorie
all_faune = df.groupby('categorie').agg({'nombre': 'sum'}).astype(int)
all_faune['angle'] = all_faune['nombre']/all_faune['nombre'].sum() * 2*pi # Calcul des angles pour chaque catégorie
all_faune['color'] = Category20b[len(all_faune)]
all_faune = ColumnDataSource(all_faune)

Birds = df[df['categorie']== 'Oiseaux']
Birds['sous_categorie'] = Birds['sous_categorie'].str.replace('Ardéidés et apparentés', 'Ardéidés')
Birds['sous_categorie'] = Birds['sous_categorie'].str.replace('Ardéidés et apparenté', 'Ardéidés')
Birds['sous_categorie'] = Birds['sous_categorie'].str.replace('Colombidés et apparentés', 'Colombidés')
#print(Birds[['date', 'sous_categorie', 'nombre']])

Birds['annee'] = pd.to_datetime(Birds['date']).dt.year # traitement de l'annee

# Grouper les données par année et sous-catégorie d'oiseaux, et calculer le nombre d'observations
grouped = Birds.groupby(["annee", "sous_categorie"])["nombre"].sum().reset_index()

types_observation = Birds['type_observation'].value_counts()

lst_Vivant = ['Vivant vue', 'Vivant Vue (VV)', 'Vivant vue (VV)', 'Cadavre Local Frais (CL)']
# on supprime toutes les observations "vivant vue" car elles ne sont pas pertinentes dans mon analyse
for i in lst_Vivant:
    if i in types_observation.index:
        types_observation.drop(i, inplace=True)

#print(types_observation)

maData = ColumnDataSource(dict(x=types_observation.index.tolist(),
                               y=types_observation.tolist(),
                               color=Category20b[len(types_observation)]))

# Graphiques -------------------------------------------------------------------------------------------------------------------------

# Camembert --------------------------------------------------------------------------------------------------------------------------
p1 = figure(height=500, width = 700, title="Répartition de la faune en Bretagne",
           toolbar_location=None, tools="hover", tooltips="@categorie: @nombre")

p1.wedge(x=0, y=1, radius=0.4, fill_color = 'color', fill_alpha = .8,
        start_angle=cumsum('angle', include_zero=True), end_angle=cumsum('angle'),
        line_color='white', source=all_faune, legend_field = 'categorie')

p1.axis.axis_label_text_font_style = 'bold'
p1.title.text_font_size = "20px"
p1.title.text_color = "cornflowerblue"
p1.legend.location = "right"
p1.legend.label_text_font_size = "8pt"
p1.legend.label_width = 100
p1.axis.visible=False # enlever les axes qui ne sont pas utiles pour un camembert
p1.toolbar.logo=None #Suppression du logo

#show(p1)

# Graphique linéaire -----------------------------------------------------------------------------------------------------------------
p2 = figure(title='Evolution temporelle du nombre d\'observations d\'oiseaux par espèce',
           x_axis_label='Année', x_range = (2016,2020),
           y_axis_label='Nombre d\'observations',
           width = 1400, height = 480, toolbar_location=None, tools="hover", tooltips="@sous_categorie: @nombre")

# Créer une ligne pour chaque sous-catégorie d'oiseaux
for espece, couleur in zip(grouped['sous_categorie'].unique(), Category20b[14]):
    df_sous_categorie = grouped[grouped['sous_categorie'] == espece]
    source_sous_categorie = ColumnDataSource(df_sous_categorie)
    ligne = p2.line(x='annee', y='nombre', source=source_sous_categorie, 
            legend_label=espece, color = couleur, line_width = 2, line_alpha = 0.8)
    

range_slider = RangeSlider(
    title="Horizon temporelle des observations",
    start=2003, end=2021, step=1, 
    value=(p2.x_range.start, p2.x_range.end)
    )
range_slider.js_link("value", p2.x_range, "start", attr_selector=0)
range_slider.js_link("value", p2.x_range, "end", attr_selector=1)

# Ajouter une légende
p2.axis.axis_label_text_font_style = 'bold'
p2.title.text_font_size = "20px"
p2.title.text_color = "cornflowerblue"
p2.legend.location = "top_left"
p2.legend.label_text_font_size = "10pt"
p2.legend.label_width = 100
p2.legend.click_policy="mute"
p2.toolbar.logo=None #Suppression du logo
#p2.legend.label_text_font_style = "bold"

#show(column(p2, range_slider))

# Carte ------------------------------------------------------------------------------------------------------------------------------
# Conversion des coordonnées géographiques en coordonnées mercator
in_proj = Proj(init='epsg:4326')
out_proj = Proj(init='epsg:3857')
lon, lat = transform(in_proj, out_proj, Birds['geo_point_2d'].apply(lambda x: x['lon']), Birds['geo_point_2d'].apply(lambda x: x['lat']))
Birds['x'] = lon
Birds['y'] = lat

# réduction de la taille des cercle
ma_liste_Birds = [x for x in Birds['sous_categorie'].unique() if x is not None]
for cat in ma_liste_Birds:
    #print(cat)
    sub_birds = Birds[Birds['sous_categorie'] == cat]
    if not sub_birds.empty:
        Birds.loc[Birds['sous_categorie'] == cat, "taille"+cat] = [val*0.5 if val >0 else 0 for val in sub_birds["nombre"]]
#print(Birds.columns)

# Créer la carte
tile_provider = get_provider(Vendors.OSM)
p3 = figure(width = 1400, height = 800, x_axis_type="mercator", y_axis_type="mercator", 
            active_scroll="wheel_zoom", title="Emplacements des observations d'oiseaux")
p3.add_tile(tile_provider)

# J'ajoute une source de donnees
matable = ColumnDataSource(Birds)

# Pour chaque sous_categorie, on fait un graphe différent
ma_legende_carte = []
couleurs = Category20b[len(ma_liste_Birds)]
for c, cat in zip(couleurs, ma_liste_Birds):
    circle = Circle(x='x', y='y', size="taille"+cat, fill_color= c, fill_alpha=0.4, line_alpha = 0.4)
    p3.add_glyph(matable, circle)
    #ma_legende_carte.append((cat, [circle]))
        
# Ajouter la légende
legend = Legend(items=ma_legende_carte, location='top_left')
p3.add_layout(legend, 'right')

# Ajouter les tooltips pour chaque cercle
p3.add_tools(HoverTool(tooltips=[('Effectif', '@nombre'), ('Sous-catégorie', '@sous_categorie')]))

# Ajouter une légende
p3.axis.axis_label_text_font_style = 'bold'
p3.title.text_font_size = "20px"
p3.title.text_color = "cornflowerblue"
p3.legend.location = "top_left"
p3.legend.label_text_font_size = "8pt"
p3.legend.label_width = 100
p3.legend.click_policy="mute"
p3.toolbar.logo=None #Suppression du logo
#p3.legend.label_text_font_style = "bold"

# Afficher la carte
#show(p)

# Graphe en barres ------------------------------------------------------------------------------------------------------------------

# Création du graphe
p4 = figure(y_range=types_observation.index.tolist(),
           plot_height=500, plot_width = 700,
           title="Mode d'observations des espèces",
           toolbar_location=None, tools="")
p4.hbar(y='x', right='y', left=0, height=0.8, source=maData,
       color='color')

p4.add_tools(HoverTool(tooltips='@x: @y'))

# Personnalisation de l'affichage
p4.xaxis.axis_label = "Nombre d'observations"
p4.yaxis.axis_label = "Type d'observation"
p4.axis.axis_label_text_font_style = 'bold'
p4.title.text_font_size = "20px"
p4.title.text_color = "cornflowerblue"
p4.toolbar.logo=None #Suppression du logo
#p4.legend.label_text_font_style = "bold"

# Affichage du graphe
#show(p4)

# Table de données -------------------------------------------------------------------------------------------------------------------
Birds1 = df[df['categorie'] == 'Oiseaux'].iloc[:, 3:]
Birds1['date'] = pd.to_datetime(Birds1['date'])
matable1 = ColumnDataSource(Birds1)
columns = [TableColumn(field=col, title=col) if col != 'date'            
           else TableColumn(field='date', title='Date', formatter=DateFormatter()) # changer la "date" en format date           
           for col in Birds1.columns]
table = DataTable(source=matable1, columns=columns, width=1400, height=800)
search_text = TextInput(title="Recherche:", value="")
search_button = Button(label="Rechercher", button_type="primary")

from bokeh.models import CustomJS

# fonction de recherche pour filtrer les donnees
def search_table():
    search_term = search_text.value.strip().lower()
    if search_term == "":
        matable1.data = Birds1.data
    else:
        data = Birds1.data
        # on filtre les donees en mettant a jour Birds1 en fonction du filtre émis
        filtered_data = {key: [value for value in data[key] if str(value).lower().find(search_term) != -1] for key in data}
        try:
            matable1.data = filtered_data
        except Exception as e:
            print(f"Error: {e}")

#search_button.callback = CustomJS(args=dict(source=matable1), code=search_table()) 

search_widgets = widgetbox([search_text, search_button], width=1400)
table_page = gridplot([[search_widgets], [table]])
#show(table_page)

# Mise en page -----------------------------------------------------------------------------------------------------------------------
entete0 = Div(text=f"\
        <h1 style='color:cornflowerblue;'>Les oiseaux en Bretagne</h1>\
        <h2 style='color:teal;'>Auteur : Bill Yehouenou #22210577</h2>\
        <p>La Bretagne est une région riche en biodiversité, notamment en ce qui concerne <b style='color:indianred;'>les oiseaux</b>. Cette région attire de nombreux passionnés d'ornithologie et des touristes venus découvrir les espèces locales. L'étude de la <a href='https://data.bretagne.bzh/explore/dataset/observations-faunistiques-sur-et-aux-abords-des-voies-navigables-bretonnes-geres/map/?location=8,48.0416,-2.83287&basemap=jawg.streets'><b>faune bretonne</b></a> est un sujet passionnant, qui permet de mieux comprendre les interactions entre les différentes espèces et leur environnement. En particulier, l'observation des oiseaux est une pratique qui permet d'en apprendre beaucoup sur leur mode de vie, leur habitat, etc... En analysant l'évolution temporelle des populations d'oiseaux par espèce, il est possible de mettre en évidence les changements environnementaux qui ont lieu dans la région. L'étude des oiseaux en Bretagne est donc un enjeu important pour la préservation de la biodiversité et la compréhension des écosystèmes locaux.</p>\
        ", style={'font-size': '15px','font-weight':'500','text-justify': 'auto','text-align':'center'})

utilite = Div(text="<p>La visualisation des données sur les oiseaux en Bretagne offre de nombreux avantages. Tout d'abord, elle permet de mieux comprendre la répartition et l'évolution des populations d'oiseaux dans la région, en mettant en évidence les zones les plus riches en biodiversité et les espèces les plus menacées. Cela permet aux chercheurs et aux autorités locales de mieux cibler les efforts de conservation et de restauration des habitats naturels. De plus, la visualisation des données sur les oiseaux peut aider à identifier les facteurs de stress environnementaux qui affectent les populations d'oiseaux, tels que la perte d'habitat, la pollution et les changements climatiques. En analysant les données à long terme, les chercheurs peuvent également évaluer l'impact des mesures de conservation et de restauration mises en place. La visualisation des données peut également être utile pour sensibiliser le grand public à la richesse de la faune bretonne et à l'importance de sa conservation. En rendant les données sur les oiseaux plus accessibles et plus compréhensibles, les citoyens peuvent mieux comprendre l'importance de la biodiversité et être encouragés à participer à des initiatives de conservation. En somme, la visualisation des données sur les oiseaux en Bretagne est un outil précieux pour la gestion de la faune et de l'environnement dans la région. Elle permet de mieux comprendre les interactions entre les différentes espèces et leur environnement, d'identifier les menaces pour la biodiversité et de mettre en place des mesures de conservation efficaces.</p>", style={'font-size': '15px','font-weight':'500','text-justify': 'auto','text-align':'center'})

entete1 = Div(text=f"\
        <h2 style='color:teal;'>Un bref récapitulatif de tout ce qu'il y a à savoir sur les oiseaux en Bretagne</h2>", style={'text-align': 'center'})

entete2 = Div(text=f"\
        <h2 style='color:teal;'>Découvrez les observations d'oiseaux en Bretagne grâce à notre carte interactive. Localisez les espèces les plus fréquentes dans la région et explorez la diversité de la faune locale. Un outil essentiel pour les ornithologues et les amoureux de la nature.</h2>", style={'text-align': 'center'})

entete3 = Div(text=f"\
        <h2 style='color:teal;'>La base de données complète de tous les oiseaux en Bretagne</h2>", style={'text-align': 'center'})

pieddepage = Div(text=f"\
        <p style='color:black;'>© 2023, Université de Rennes - Master 1 Mathématiques Appliquées, Statistiques</p>", style={'font-size': '14px','text-justify': 'auto','text-align': 'center'})

# Création des div pour les images
img1 = Div(text="<img src='oiseaux_images/img1.jpg' title='Mouette rieuse' style='width: 350px; height: 600px;'>")
img2 = Div(text="<img src='oiseaux_images/img2.jpg' title='Héron cendré' style='width: 350px; height: 600px;'>")
img3 = Div(text="<img src='oiseaux_images/img3.jpg' title='Macareux moine' style='width: 350px; height: 600px;'>")
img4 = Div(text="<img src='oiseaux_images/img4.jpg' title='Bulbul orphée' style='width: 350px; height: 600px;'>")

grid0 = gridplot([[entete0],[row(img1, img2, img3, img4)],[utilite],[pieddepage]])
grid1 = gridplot([[entete1],[row(p1,p4)],[column(p2, range_slider)], [pieddepage]]) # Créer la grille de graphe
grid2 = gridplot([[entete2], [p3], [pieddepage]])
grid3 = gridplot([[entete3],[table_page], [pieddepage]])

mapage0 = Panel(child=grid0, title = "Contexte")
mapage1 = Panel(child=grid1, title = "Visualisation des données")
mapage2 = Panel(child=grid2, title = "Cartographie")
mapage3 = Panel(child=grid3, title= "Table de données")
monSiteBokeh = Tabs(tabs = [mapage0,mapage1,mapage2,mapage3])
show(monSiteBokeh, logo=None)

