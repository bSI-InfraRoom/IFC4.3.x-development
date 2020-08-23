IfcMapConversion
================
The map conversion deals with transforming the local engineering coordinate
system, often called world coordinate system, into the coordinate reference
system of the underlying map.  
  
> NOTE  The _IfcMapConversion_ does not handle the projection of a map from
> the geodetic coordinate reference system.  
  
The map conversion allows to convert the local origin of the local engineering
coordinate system to its place within a map (easting, northing, orthogonal
height) and to rotate the x-axis of the local engineering coordinate system
within the horizontal (easting/westing) plane of the map.  
  
> NOTE  The z axis of the local engineering coordinate system is always
> parallel to the z axis of the map coordinate system.  
  
The scale factor can be used when the length unit for the 3 axes of the map
coordinate system are not identical with the length unit established for this
project (see\S\ _IfcProject.UnitsInContext_), if omitted, the scale factor 1.0
is assumed.  
  
> HISTORY  New entity in IFC4  
[ _bSI
Documentation_](https://standards.buildingsmart.org/IFC/DEV/IFC4_2/FINAL/HTML/schema/ifcrepresentationresource/lexical/ifcmapconversion.htm)


Attribute definitions
---------------------
| Attribute        | Description                                                                                                                                                                                                                                                                                                                                                                                                                                  |
|------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Eastings         | Specifies the location along the easting of the coordinate system of the target map coordinate reference system.\X\0D> NOTE  for right-handed Cartesian coordinate systems this would establish the location along the x axis.                                                                                                                                                                                                               |
| Northings        | Specifies the location along the northing of the coordinate system of the target map coordinate reference system.\X\0D> NOTE  for right-handed Cartesian coordinate systems this would establish the location along the y axis                                                                                                                                                                                                               |
| OrthogonalHeight | Orthogonal height relativ to the vertical datum specified.\X\0D> NOTE  for right-handed Cartesian coordinate systems this would establish the location along the z axis                                                                                                                                                                                                                                                                      |
| XAxisAbscissa    | Specifies the value along the easing axis of the end point of a vector indicating the position of the local x axis of the engineering coordinate reference system.\X\0D> NOTE 1 for right-handed Cartesian coordinate systems this would establish the location along the x axis\X\0D\X\0D> NOTE 2 together with the _XAxisOrdinate_ it provides the direction of the local x axis within the horizontal plane of the map coordinate system  |
| XAxisOrdinate    | Specifies the value along the northing axis of the end point of a vector indicating the position of the local x axis of the engineering coordinate reference system.\X\0D> NOTE 1 for right-handed Cartesian coordinate systems this would establish the location along the y axis\X\0D\X\0D{ .note}\X\0D> \X\0D\X\0D_XAxisAbscissa_ it provides the direction of the local x axis within the horizontal plane of the map coordinate system. |
| Scale            | Scale to be used, when the units of the CRS are not identical to the units of the engineering coordinate system. If omited, the value of 1.0 is assumed.                                                                                                                                                                                                                                                                                     |
