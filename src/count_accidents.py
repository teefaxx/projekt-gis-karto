import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
from shapely.ops import nearest_points
import numpy as np


def read_data():
    # Read in data
    master = gpd.read_file('../export/results/results_bfs.geojson')
    accidents = gpd.read_file('../export/accidents/accidents.geojson')

    # Add column to master_table
    master['GDE_CNTR'] = master.apply(
        lambda row: Point(row['E_CNTR'], row['N_CNTR']), axis=1)
    master['ACCIDENTS'] = 0

    return master, accidents


def count_accs(master, accidents):
    joined = gpd.sjoin(master, accidents, op='contains')

    # Count the number of accidents within each polygon
    counts = joined.groupby('GMDNR').size().reset_index(name='ACCIDENTS')

    # Merge the counts back into the master GeoDataFrame
    master = master.merge(counts, on='GMDNR', how='left')

    master = master.drop(columns='ACCIDENTS_x', axis=1)
    master = master.rename(columns={'ACCIDENTS_y': 'ACCIDENTS'})

    return master


def export_accidents(master):
    master = master.drop(columns='GDE_CNTR', axis=1)
    master.to_file(
        '../export/master/master_with_accidents.geojson', driver='GeoJSON')
    print('Dataframe exported...')


if __name__ == '__main__':
    master, accidents = read_data()
    master = count_accs(master, accidents)
    export_accidents(master)
