import pandas as pd
import geopandas as gpd
import os

'''
This file is used to get the bike data from the OSM and the Veloland data.

RETURNS: 
    - GeoJSON with all the bike data
'''


def read_osm():
    osm_data = gpd.read_file(
        '../../data/OSM_new/switzerland-latest-free.shp/gis_osm_roads_free_1.shp')  # Read file
    osm_data = osm_data[osm_data['code'] == 5152]  # Filter for cycleways
    osm_data = osm_data.to_crs('epsg:2056')  # Change to LV95
    keep_cols = ['osm_id', 'code', 'geometry']
    osm_data = osm_data.drop(
        columns=[col for col in osm_data.columns if col not in keep_cols])  # Filter Cols
    osm_data = osm_data.rename(columns={'osm_id': 'OBJECTID'})
    return osm_data


def read_veloland():
    veloland = gpd.read_file('../../data/Velo/veloland_2056.shp/Weg.shp',
                             geometry='geometry', crs='epsg:2056')  # Read data
    keep_cols = ['OBJECTID', 'SHAPE_Leng', 'Change_Dt', 'geometry']
    veloland = veloland.drop(
        columns=[col for col in veloland.columns if col not in keep_cols])  # Filter Cols
    return veloland


def concat_bike(osm_data, veloland):
    bikes = pd.concat([osm_data, veloland])
    return bikes


def export_df(df_in):
    df_in.to_file('export/velo/bikes.geojson', driver='GeoJSON')
    return print("Created GeoJSON...")


if __name__ == "__main__":
    export_df(concat_bike(read_osm(), read_veloland()))
