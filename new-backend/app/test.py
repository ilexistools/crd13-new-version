from app.tools.commodities_identification import CommoditiesIdentifierTool
from app.tools.unitization import UnitizationTool
from app.tools.provisions_search import ProvisionsSearchTool

commodities_identifier = CommoditiesIdentifierTool()
unitizer = UnitizationTool()
provisions_identifier = ProvisionsSearchTool()

text ="The meat has derived from animals reared in country/ zone which is free from foot-and-mouth disease (with or without vaccination), African swine fever and classical swine fever, and which have been slaughtered, processed, packaged and stored under hygienic conditions under official veterinary supervision in establishments authorised by the Director-General of the Food Administration for export to China."

#text = "Milk and milk products must be produced from animals reared in country/ zone which is free from foot-and-mouth disease (with or without vaccination), African swine fever and classical swine fever, and which have been slaughter"

text = "Fish products must be free from contamination."

commodities = commodities_identifier.run(text)

print("Commodities identified:")
for commodity in commodities['results']:
    print(commodity)

units = unitizer.run(text)

print("Units identified:")
for unit in units['results']:
    print(unit)

print("Provisions identified:")
commodities =['fish']
provisions_search = ProvisionsSearchTool()
provisions = provisions_search.run(commodities, text)
for provision in provisions:
    print([provision['rank'], provision['relevance'],provision['sentence'], provision['modality']])
    print('')