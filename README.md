# Projekt GIS & Kartografie

### [**Projektbericht**](FS23_Proj_GIS_Karto_Bericht_Dario_DeLuca)
#### Abstract

Im Rahmen des Projekts «GIS & Kartografie» befasst sich dieser Bericht mit der räumlichen Analyse der schweizerischen Abstimmungsergebnisse über den Bundesbeschluss zu Velowegen sowie Fuss- und Wanderwegen. Ziel der Analyse ist es, den Zusammenhang zwischen der Anzahl der Ja-Stimmen und dem Vorhandensein von Veloinfrastrukutr in den Gemeinden zu untersuchen. Die Analyse basiert auf verschiedenen Datenquellen wie Abstimmungsdaten, Informationen zu Fahrradwegen und Unfallstatistiken. Die Ergebnisse werden mithilfe von Choroplethenkarten und Kreisdiagrammen visuell dargestellt, um einen umfassenden Überblick über den Zusammenhang zu geben. Die Ergebnisse zeigen, dass kein statistisch signifikanter Zusammenhang zwischen der Anzahl der Ja-Stimmen und dem Vorhandensein von Fahrradinfrastruktur oder den Unfallraten besteht. Vielmehr haben sozioökonomische Aspekte einen Einfluss auf die Abstimmungsresultate.


## Ablauf der Datenanalyse

**[Zip-Ordner](https://we.tl/t-W3g6WK0sIz?utm_campaign=TRN_TDL_05&utm_source=sendgrid&utm_medium=email&trk=TRN_TDL_05) herunterladen und in Git Ordner ziehen [Link valide bis 9. Juni 2023 at 18:20]** (Dateien zu gross für Upload via GitHub)**.**

**Unzip [data.zip](data.zip) um Code laufen zu lassen.**

1. [results_data.py](src/get_data/results_data.py) &rarr; [results_bfs.geojson](export/results/results_bfs.geojson)
2. [bike_data.py](src/get_data/bike_data.py) &rarr; [bikes.geojson](export/velo/bikes.geojson)
3. [accidents_data](src/get_data/accidents_data.py) &rarr; [accidents.geojson](export/accidents/accidents.geojson)
4. [count_accidents](src/count_accidents.py) &rarr; [master_with_accidents.geojson](export/master/master_with_accidents.geojson)
5. Zwischenschritt in ArcGIS (Aufsummierung Velowege pro Gemeinde)
6. [add_bike.py](src/add_bike.py) &rarr; [master_acc_bike.geojson](export/master/master_acc_bike.geojson)
7. [results_data.py](src/get_data/results_data.py) &rarr; [results_bfs.geojson](export/results/results_bfs.geojson)
8. Zwischenschritt in QGIS (Ausummierung der Verkehrswege pro Gemeinde)
9. [values.py](src/map_values.py) &rarr; [final_values.geojson](export/final_values.geojson)
10. [corr.py](src/corr.py)
11. [plots.py](src/plots.py) &rarr; [plots/](export/plots/)


## Erstellung Karte

Im Ordner [map](map/) sind die [QGIS-Dateien](map/QGIS) und die [Affinity Designer / Illustrator Dateien](map/Affinity_Illustrator) enthalten.
