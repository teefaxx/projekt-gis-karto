import pandas as pd
import geopandas as gpd
import os


'''
This file is used to get the results of the vote and the BFS geometries.

RETURNS:
    - GeoJSON with all the results and the BFS geometries

'''


def get_bfs():
    # Reads in the BFS Shapefile and keeps the needed columns
    bfs = gpd.read_file('../../data/shp_bfs/g1g23.shp',
                        geometry='geometry', srs='epsg:2056')
    keep_cols = ['GMDNR', 'GMDNAME', 'BZNR',
                 'KTNR', 'E_CNTR', 'N_CNTR', 'geometry']
    bfs = bfs.drop(
        columns=[col for col in bfs.columns if col not in keep_cols])

    return bfs


def get_results():
    # Reads in the Results of the vote and keeps the needed columns
    results = pd.read_excel('../../data/results/Resultate.xlsx',
                            sheet_name='data', header=0)
    results = results.dropna(axis=0)

    df = results.loc[~results['GMDNAME'].str.startswith('>>')]
    df = df.loc[~df['GMDNAME'].str.startswith('-')]
    df['GMDNAME'] = df['GMDNAME'].str[6:]
    df = df.drop(index=0)
    df['GMDNR'] = df['GMDNR'].astype(int)

    df_out = gpd.GeoDataFrame(df)

    return df_out


def merge_data(bfs, results):
    # Merges the two dataframes
    merged_df = pd.merge(results, bfs, on=['GMDNR'])
    merged_gp = gpd.GeoDataFrame(
        merged_df, crs='epsg:2056', geometry='geometry')

    return merged_gp


def export_merged_df(df_in):
    # Exports the merged dataframe as GeoJSON
    df_in.to_file('../../export/results/results_bfs.geojson',
                  driver='GeoJSON', epsg=2056)
    return print('Dataframes (merged) exported to ../../export/results/results_bfs.geojson')


if __name__ == '__main__':
    export_merged_df(merge_data(get_bfs(), get_results()))
