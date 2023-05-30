import geopandas as gpd
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib import cm


def read_data():
    df = gpd.read_file('../export/final_values.geojson')

    return df


def plot_corr(df_in, x_values, y_values, title, x_label, y_label, dot_color, reg_color, filename):
    df_in.plot.scatter(x=x_values, y=y_values, figsize=(
        10, 10), legend=True, c=dot_color)

    plt.title(title)

    plt.grid(True)

    sns.regplot(data=df_in, x=x_values, y=y_values,
                scatter=False, color=reg_color)
    plt.xlabel(x_label)
    plt.ylabel(y_label)

    plt.savefig(f'../export/plots/{filename}.png')

    return plt.show()


if __name__ == '__main__':
    data = read_data()
    bike_paths = {
        'x_values': 'YES_IN_PER',
        'y_values': 'BIKE_STREET_PER',
        'title': 'Zusammenhang zwischen Ja-Stimmen und Veloweg-Anteil',
        'x_label': 'Ja-Stimmen in %',
        'y_label': 'Veloweg-Anteil in %',
        'dot_color': 'blue',
        'reg_color': 'red',
        'filename': 'bike_path_corr'
    }

    accidents = {
        'x_values': 'YES_IN_PER',
        'y_values': 'ACCIDENTS_PER_100K',
        'title': 'Zusammenhang zwischen Ja-Stimmen und Velounfällen',
        'x_label': 'Ja-Stimmen in %',
        'y_label': 'Velounfälle pro 100k Einwohner',
        'dot_color': 'blue',
        'reg_color': 'red',
        'filename': 'accidents_corr'
    }

    plot_corr(data, **bike_paths)
    plot_corr(data, **accidents)
