from app.tools.unitization import UnitizationTool

unitizer = UnitizationTool()

text = """
The product was manufactured in facilities inspected and approved by the competent authority and subjected to regular audits or inspections aimed at ensuring that the processing is properly and hygienically carried out, to produce a product that is fit for human consumption.
The product was manufactured from milk or milk products that received a pasteurization treatment or adequate safeguards have been taken with the aim of avoiding public health hazards arising from pathogenic organisms associated with milk.
To the best of our knowledge, the product contains no harmful levels of contaminants.
"""

output = unitizer.run(text)

print("Unitization Results:")
for i, unit in enumerate(output['results'], start=1):
    print(f"Unit {i}: {unit}")



