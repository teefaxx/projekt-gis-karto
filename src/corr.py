import geopandas as gpd
import pandas as pd
import numpy as np


def read_data():
    df = gpd.read_file('../export/final_new.geojson')

    return df


def acc_per100k(df_in):
    df = df_in.copy()
    df = df.fillna(0)
    df['ACC_PER_100K'] = (df['ACCIDENTS'] / df['POP_TOTAL']) * 100_000
    df_out = df.replace([np.inf, -np.inf], 0)

    return df_out


def correlation(df_in):
    corr_paths = df_in['YES_IN_PER'].corr(df_in['BIKE_STREET_PER'])
    corr_acc = df_in['YES_IN_PER'].corr(df_in['ACC_PER_100K'])

    return corr_paths, corr_acc


if __name__ == '__main__':
    print(correlation(acc_per100k(read_data())))
