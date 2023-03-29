import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
from shapely.ops import nearest_points
import numpy as np


def read_data():
    master = gpd.read_file('../../export/master.geojson')
    accidents = gpd.read_file('../../export/accidents/accidents.geojson')

    # Add column to master_table
    master['GDE_CNTR'] = master.apply(
        lambda row: Point(row['E_CNTR'], row['N_CNTR']), axis=1)
    master['smaller_2'] = 0
    master['2_to_5'] = 0
    master['5_to_10'] = 0

    return master, accidents


def calc_distance(gdf1, gdf2):
    return gdf1.geometry.apply(lambda x: gdf2.distance(x))


def distance(mas, acc):
    distances = calc_distance(mas, acc)

    # count the number of distances that fall into each distance category using boolean indexing
    mas['smaller_2'] = (distances < 2000).sum(axis=1)
    mas['2_to_5'] = ((distances >= 2000) & (distances < 5000)).sum(axis=1)
    mas['5_to_10'] = ((distances >= 5000) & (distances < 10000)).sum(axis=1)

    return mas


def export_master(master):
    master = master.drop(columns='GDE_CNTR', axis=1)
    master.to_file('../../export/master_with_acc_test.geojson',
                   driver='GeoJSON')
    print('Dataframe exported...')


if __name__ == '__main__':
    mas, acc = read_data()
    export_master(distance(mas, acc))
