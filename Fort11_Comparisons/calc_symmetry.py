from netCDF4 import Dataset
import numpy as np

nc1 = Dataset('fort.11.nc', 'r')
nc2 = Dataset('fort.11_und.nc', 'r')

# Check all variables
for var in ['BPGX', 'BPGY', 'MLD', 'SigTS']:
    if var in nc1.variables and var in nc2.variables:
        var1 = nc1.variables[var][:]
        var2 = nc2.variables[var][:]
        diff = var2 - var1
        diff_min = np.nanmin(diff)
        diff_max = np.nanmax(diff)
        abs_max = max(abs(diff_min), abs(diff_max))
        print(f"\n{var} Difference Range:")
        print(f"  Min: {diff_min:.6e}")
        print(f"  Max: {diff_max:.6e}")
        print(f"  Symmetric range: ±{abs_max:.6e}")

nc1.close()
nc2.close()
