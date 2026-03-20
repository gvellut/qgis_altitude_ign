I want a QGIS plugin (for QGIS 3). It will be a simple button in the plugin toolbar, as well as a submenu below the Plugin menu
- when button active : 
- the cursor transforms into a cross
- A panel Altitude IGN appears with an empty text field and a button Copy (the icon 2 squares that overlap)
- when the user clicks on the map : a request to : 

https://data.geopf.fr/altimetrie/1.0/calcul/alti/rest/elevation.json?lon=1.4&lat=43.54&resource=ign_rge_alti_wld&zonly=true

is made. lon=1.4&lat=43.54 are the coorrdinates of the clicked point in WGS84

Response is :
{"elevations": [149.55]}

The elevation is put in a text field

- Copy button copy the field.
- If another field : the text field is overwrittend
- The plugin deactivate if another tool becomes active (standard behaviour)