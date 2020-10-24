from osgeo import ogr
import xarray as xr
from sys import argv
import shapely.geometry as geom
from shapely.affinity import translate
import numpy as np
from pandas import Timestamp

#######################################################################
# Remap data from a WGS84 lat/lon worldwide grid
# to irregular shapefiles in WGS84 or NAD83 lat/lon CRS
#######################################################################

if len(argv) < 8:
    print("""Arguments : 
    1 : Shapefile path
    2 : netCDF file path
    3 : netCDF x (lon) resolution
    4 : netCDF y (lat) resolution
    5 : First latitude, in degrees (should be either 90 or -90)
    6 : Output file name for shape properties
    7 : Output file name for data""")
    quit()

shapePath = argv[1]
gridPath = argv[2]
xRes = float(argv[3])
yRes = float(argv[4])
firstLat = float(argv[5])
outPropName = argv[6]
outDataName = argv[7]

maxI = 360//xRes
maxJ = 180//yRes

print("Extracting shape data...")
# Collect shape data
shapeData = []
ds = ogr.Open(shapePath)
for i in range(ds.GetLayerCount()):
    layerData = []
    layer = ds.GetLayer(i)

    for j in range(layer.GetFeatureCount()):
        # GeoJSON is a convenient format compatible with many other python modules.
        # To get the actual Feature object, simply use "feat = layer.GetFeature(j)"
        feat = layer.GetFeature(j).ExportToJson(as_object=True)

        layerData.append(feat)
    
    shapeData.append(layerData)

"""
# Shapefile data is now ready to explore.
# Everything in shapeData is now a python object
example = shapeData[0][0]

print(example["type"]) # "Feature"
print(example["geometry"]) # The actual object geometry as a GeoJSON (can be passed to folium and shapely)
print(example["properties"]) # Other properties associated to the object (e.g. FIPS, State, Country)
print(example["id"]) # Object ID in the shapefile
"""
# Convert shape data to shapely objects
for layer in shapeData:
    for shape in layer:
        shapeGeom = shape["geometry"]
        shapeGeom = geom.shape(shapeGeom)
        if shapeGeom.bounds[2] < 0:
            shapeGeom = translate(shapeGeom,xoff=360)
        shape["geometry"] = shapeGeom

        brec = shapeGeom.bounds # minx,miny,maxx,maxy
        if firstLat > 0:
            shape["overlap"] = ([int((brec[0] // xRes) % maxI),int((brec[2] // xRes + 1) % maxI)],(int(max(0,(90-brec[3]) // yRes)),int(min(maxI,(90-brec[1]) // yRes + 1))))
        else:
            shape["overlap"] = ([int((brec[0] // xRes) % maxI),int((brec[2] // xRes + 1) % maxI)],(int(max(0,(brec[1] + 90) // yRes)),int(min(maxI,(brec[3] + 90) // yRes + 1))))
        if shape["overlap"][0][1] < shape["overlap"][0][0]:
             shape["overlap"][0][0] = 0
             shape["overlap"][0][1] = maxI - 1

print("Calculating grid polygons...")
# Open netCDF
ds = xr.open_dataset(gridPath)

# whatever -> longitude,latitude,time
lons = None
lats = None
times = None
for dim in ds.coords:
    if dim == "longitude":
        lons = ds.coords[dim].values
    elif dim == "latitude":
        lats = ds.coords[dim].values
    elif dim == "time":
        times = ds.coords[dim].values

# Create grid polygons
grid = np.empty((len(lons),len(lats)),dtype=object)

# Presumes firstLat is positive.
for i in range(len(lons)):
    for j in range(len(lats)):
        grid[i][j] = geom.Polygon(((lons[i],lats[j]),(lons[i] + xRes,lats[j]),(lons[i] + xRes,lats[j] - yRes),(lons[i],lats[j] - yRes),(lons[i],lats[j])))

print("Calculating grid overlap with shapes...")
# TODO : Pre-calculate area proportion
for layer in shapeData:
    for shape in layer:
        overlap = shape["overlap"]
        shapeGeom = shape["geometry"]
        #print(shapeGeom)
        xMin = int(overlap[0][0])
        xMax = int(overlap[0][1])
        yMin = int(overlap[1][0])
        yMax = int(overlap[1][1])
        tmp = np.zeros((xMax-xMin,yMax-yMin))
        #print(shape["properties"])
        #print(shapeGeom.bounds)
        for i in range(xMin,xMax):
            for j in range(yMin,yMax):
                #print(grid[i][j].bounds)
                tmp[i-xMin][j-yMin] = grid[i][j].intersection(shapeGeom).area / shapeGeom.area
        shape["overlapMat"] = tmp
        test = np.sum(tmp)
        #print(tmp)
        if test < 0.9999 or test > 1.0001:
            if test > 0.95:
                shape["overlapMat"] /= test
            else:
                print(shape["properties"])
                del shape["overlapMat"]

print("Remapping grid data to shapes...")
# Remap grid data to shapes
data = dict()
dataProperties = dict()


for var in ds:
    vals = np.transpose(ds[var].values,(0,2,1)) # Time, Lon, Lat
    print("Processing " + var)
    print(vals.shape)

    for layer in shapeData:
        for shape in layer:
            if "overlapMat" in shape:
                shapeID = shape["id"]
                if shapeID not in data:
                    data[shapeID] = dict()
                    dataProperties[shapeID] = shape["properties"]
                    data[shapeID][var] = []

                shapeDict = data[shapeID]

                if var not in shapeDict:
                    shapeDict[var] = []

                shapeVar = shapeDict[var]

                overlap = shape["overlap"]
                xMin = overlap[0][0]
                xMax = overlap[0][1]
                yMin = overlap[1][0]
                yMax = overlap[1][1]
                overlapMat = shape["overlapMat"]

                try:
                    for i,time in enumerate(times):
                        tmp = vals[i,xMin:xMax,yMin:yMax]
                        if tmp.shape != overlapMat.shape:
                            tmp = vals[i,xMin:xMin + overlapMat.shape[0]+1,yMin:yMin + overlapMat.shape[1]+1]
                        shapeVar.append((Timestamp(str(time)),np.sum(tmp * overlapMat)))
                except:
                    print(xMin,xMax,yMin,yMax,vals.shape)
                    print("Could not process shape " + str(shape["properties"]) + " for variable " + var + " at time " + str(time) + ".")

entries = dict()

netVars = set()
propVars = set()

for shID in data:
    for prop in dataProperties[shID]:
        propVars.add(prop)
    for var in data[shID]:
        netVars.add(var)
        for time,val in data[shID][var]:
            key = (shID,str(time))
            if key not in entries:
                entries[key] = dict()
            entries[key][var] = val

f = open(outPropName,"w")

headers = ["shapeID"]

propVars = list(sorted(propVars))

headers.extend(propVars)

f.write(",".join(headers) + "\n")

for entry in dataProperties:
    line = [str(entry)]
    entryDict = dataProperties[entry]
    for prop in propVars:
        if prop in entryDict:
            line.append(str(entryDict[prop]))
        else:
            line.append("")

    f.write(",".join(line) + "\n")

f.close()

f = open(outDataName,"w")

headers = ["shapeID","time"]

netVars = list(sorted(netVars))

headers.extend(netVars)

f.write(",".join(headers) + "\n")

for entry in entries:
    line = [str(entry[0]),entry[1]]
    entryDict = entries[entry]
    for var in netVars:
        if var in entryDict:
            line.append(str(entryDict[var]))
        else:
            line.append(str(np.nan))

    f.write(",".join(line) + "\n")

f.close()