# To add a new cell, type '# %%'
# To add a new markdown cell, type '# %% [markdown]'

# %%
from bokeh.plotting import figure, show, output_file
from bokeh.sampledata.us_counties import data as counties
from bokeh.sampledata.us_states import data as states
import pandas as pd

df_covid = pd.read_csv('./prediction_results.csv')

EXCLUDED = ("ak", "hi", "pr", "gu", "vi", "mp", "as")

state_xs = [states[code]["lons"] for code in states]
state_ys = [states[code]["lats"] for code in states]

county_xs=[counties[code]["lons"] for code in counties if counties[code]["state"] not in EXCLUDED]
county_ys=[counties[code]["lats"] for code in counties if counties[code]["state"] not in EXCLUDED]

colors = ['green', 'blue', 'red']

df_covid_date =  df_covid[df_covid.date_begin == '2020-03-29']
county_colors = []
for county_id in counties:
    if counties[county_id]["state"] in EXCLUDED:
        continue
    fips = county_id[0]*1000 + county_id[1]
    pred = df_covid_date[df_covid.FIPS == fips].predicted.values
    if len(pred) != 0:
        county_colors.append(colors[pred[0]])
    else:
        county_colors.append("black")

p = figure(title="US Unemployment 2009", toolbar_location="left",plot_width=1100, plot_height=700, x_range=(-79, -68), y_range=(38, 45))
p.patches(county_xs, county_ys,fill_color=county_colors, fill_alpha=0.7,line_color="white", line_width=0.5)
p.patches(state_xs, state_ys, fill_alpha=0.0,line_color="#884444", line_width=2, line_alpha=0.3)
output_file("choropleth.html", title="choropleth.py example")

show(p)


