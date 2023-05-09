import geopandas as gpd
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


def read_data():
    df = gpd.read_file('../export/master/master_acc_bike_pop_street.geojson')

    return df


def acc_per100k(df_in):
    df = df_in.copy()
    df = df.fillna(0)
    df['ACCIDENTS_PER_100K'] = df['ACCIDENTS'] / \
        df['POP_TOTAL'] * 100000
    df_out = df.replace([np.inf, -np.inf], 0)

    return df_out


def percentage(df_in):
    df = df_in.copy()

    # Change types etc.
    df = df.replace('...', 0)
    df = df.fillna(0)
    df['YES_IN_PER'] = df['YES_IN_PER'].astype(float)
    df['BIKE_STREET_PER'] = df['BIKE_STREET_PER'].astype(float)

    # Change percentages to decimals
    df['YES_IN_PER'] = df['YES_IN_PER'] / 100
    df['BIKE_STREET_PER'] = df['BIKE_STREET_PER'] / 100

    return df


def comparison(df_in):
    #mean_yes = np.round(df.YES_IN_PER.mean(),2)
    df = df_in.copy()
    mean_yes = np.round(df.YES_IN_PER.mean(), 2)
    print(mean_yes)

    velo = [0.0499, 0.0538, 0.07373, 0.07689, 0.06192, 0.07163]
    # https://www.prixvelo.ch/de/prix-velo-infrastruktur
    # 0.0499 Biel
    # 0.0538 Chur
    # 0.07373 Solothurn
    # 0.07689 Basel
    # 0.06192 Luzern
    # 0.07163 Bern
    good_bike = np.mean(velo)

    #good_bike = df.BIKE_STREET_PER.quantile(0.66)
    #good_bike = df.BIKE_STREET_PER.mean()

    #df['VALUE'] = 0

    # Use boolean indexing to set initial value of VALUE column
    #df.loc[df.BIKE_STREET_PER >= good_bike, 'VALUE'] = 1
    #df.loc[df.BIKE_STREET_PER < good_bike, 'VALUE'] = -1

    # Use boolean indexing to update VALUE column based on conditions
    df.loc[(df.BIKE_STREET_PER >= good_bike) & (
        df.YES_IN_PER >= mean_yes), 'VALUE'] = 2
    df.loc[(df.BIKE_STREET_PER >= good_bike) & (
        df.YES_IN_PER < mean_yes), 'VALUE'] = 1
    df.loc[(df.BIKE_STREET_PER < good_bike) & (
        df.YES_IN_PER >= mean_yes), 'VALUE'] = 0
    df.loc[(df.BIKE_STREET_PER < good_bike) & (
        df.YES_IN_PER < mean_yes), 'VALUE'] = -1

    return df  # , round(good_bike*100, 2)


def export(df_in):
    df = df_in.copy()

    keep_cols = ['BFSNR', 'YES_IN_PER', 'BIKE_STREET_PER',
                 'ACCIDENTS', 'POP_TOTAL', 'GMDNAME', 'BZNR', 'KTNR', 'E_CNTR', 'N_CNTR', 'geometry']

    df = df[keep_cols]
    df.to_file('../export/final_new.geojson', driver='GeoJSON')

    return print('Dataframe exported to ../export/final.geojson')


if __name__ == '__main__':
    df = read_data()
    df = percentage(df)
    df = acc_per100k(df)
    df = comparison(df)
    export(df)

    # print(df.head())
