from sklearn.preprocessing import scale
from sklearn.decomposition import PCA
import numpy as np
import pandas as pd
from pathlib import Path

# -- FETCH --
print("FETCHING DF")
DATA_FOLDER = "./data/"
CAMS_FOLDER = DATA_FOLDER + "cams/"

CAMS_CSVs = ["10_oct.csv",  "3_mar.csv",  "6_jun.csv",  "9_sept.csv",
             "1_jan.csv",   "4_apr.csv",  "7_jul.csv",
             "2_feb.csv",   "5_may.csv",  "8_aug.csv"]
df = pd.DataFrame()
for csv in CAMS_CSVs:
    df = pd.concat([df, pd.read_csv(CAMS_FOLDER + csv)], ignore_index=True)

props = pd.read_csv(CAMS_FOLDER + "shape_properties.csv")


# -- AOD --
print("PROCESSING AODS")
aodSums = None
AODs = [column for column in df.columns if "aod" in column and column != "aod550"]

for aod in AODs:
    if aodSums is None:
        aodSums = df[aod].copy()
    else:
        aodSums += df[aod]
for aod in AODs:
    df[aod] /= aodSums
for AOD in AODs:
    df[AOD] = -np.log(1.0/(1e-14 + df[AOD]*(1.0 - 2e-14)) - 1)
df["aod550"] = np.log(df["aod550"] + 1e-15)


# -- PM ---
print("PROCESSING PMs")
# kg/m^3 -> µg/m^3
df["pm1"] *= 10**9
df["pm2p5"] *= 10**9
df["pm10"] *= 10**9
pms = ["pm1", "pm2p5", "pm10"]
for pm in pms:
    df[pm] = np.log10(df[pm] + 1e-15)


# -- TCS --
print("PROCESSING TCs")
# To nearest unit
tcs = [column for column in df.columns if column[:2] == "tc"]
for tc in tcs:
    maxLog = np.log10(df[tc].max())//3
    maxLog *= 3
    df[tc] *= 10**-maxLog
for tc in tcs:
    df[tc] = np.log10(df[tc] + 1e-15)

df["time"] = pd.to_datetime(df["time"])
df = df.sort_values(["shapeID", "time"])


# -- PCA --
N_PC = 11
col_names = df.columns.drop(["shapeID","time","tc_ch4","tc_c2h6","tc_c3h8","tc_c5h8"])
# get vals and Standardize for PCA
print("DOING SCALING")
data = scale(np.matrix(df[col_names].values))
print("DOING PCA")
x = PCA(n_components=N_PC).fit_transform(data)


# -- EXPORT --
print("CREATING CSVs")
X = pd.DataFrame(df[["shapeID", "time"]])
for i in range(N_PC):
    X["x"+str(i)] = x[:, i]
print("EXPORTING CSVs")
X.to_csv(DATA_FOLDER + "X/cams_data.csv")
