from ietfdata.datatracker import *

dt = DataTracker(
    DTBackendArchive(r"C:\Users\ZHZ\Desktop\IETF-DISSERTATION\data\ietfdata-dt.sqlite")
)

d = dt.document_from_rfc("RFC9000")

print("Title:", d.title)
print("Name:", d.name)
print("Group:", d.group)

g = dt.group(d.group)
print("Group acronym:", g.acronym)
print("Group name:", g.name)