import pandas as pd
import geopandas as gpd
from shapely import wkt
import os

'''
This file is used to get tha data from the accidents in Switzerland.
The data is filtered by year (until 2018) and by mode (only bicycle).

RETURNS: 
    - GeoJSON with all the accidents
'''


def read_data(export=False):
    df = gpd.read_file(
        '../../data/accidents/accidents.json')

    keep_cols = ['AccidentType_de', 'AccidentSeverityCategory_de', 'AccidentInvolvingPedestrian', 'AccidentInvolvingBicycle',
                 'RoadType_de', 'AccidentLocation_CHLV95_E', 'AccidentLocation_CHLV95_N', 'CantonCode', 'AccidentYear', 'AccidentMonth', 'geometry']
    gdf = df.drop(columns=[col for col in df.columns if col not in keep_cols])

    # Typechange of DF
    gdf['AccidentInvolvingBicycle'] = gdf['AccidentInvolvingBicycle'].str.lower(
    ).map({'true': True, 'false': False})
    gdf['AccidentInvolvingPedestrian'] = gdf['AccidentInvolvingPedestrian'].str.lower(
    ).map({'true': True, 'false': False})
    gdf.AccidentYear = gdf.AccidentYear.astype(int)
    gdf.AccidentMonth = gdf.AccidentMonth.astype(int)
    gdf.AccidentLocation_CHLV95_E = gdf.AccidentLocation_CHLV95_E.astype(int)
    gdf.AccidentLocation_CHLV95_N = gdf.AccidentLocation_CHLV95_N.astype(int)

    # Filtering DF
    gdf = gdf[(gdf['AccidentMonth'] <= 9) & (gdf['AccidentYear'] <= 2018)]
    gdf = gdf[gdf['AccidentInvolvingBicycle']]

    # Change CRS to LV95
    gdf = gdf.set_crs(gdf.crs)
    geometry = gpd.points_from_xy(
        gdf['AccidentLocation_CHLV95_E'], gdf['AccidentLocation_CHLV95_N'], crs='epsg:2056')
    gdf.geometry = geometry

    if export:
        gdf.to_file('../../export/accidents/accidents.geojson', index=False)
        print('Dataframe exported...')
    else:
        return print(gdf.head())


if __name__ == '__main__':
    read_data(export=True)
