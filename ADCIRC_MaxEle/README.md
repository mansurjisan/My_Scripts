### For Global domain:

```bash
python plot_maxele.py maxele.63_mji_720.nc maxele.63_undnew.nc zeta_max     --region global     --vmin -0.01 --vmax 0.01        --color-levels 20     --no-individual     --max-points 0 --highlight-extremes    --save new_adc_und_maxele.png

```

### For regional

```bash
python plot_maxele.py maxele1.nc maxele2.nc zeta_max --region custom --lon-range -85 -65 --lat-range 25 45    --vmin -0.01 --vmax 0.01 --color-levels 20     --max-points 0 --dpi 300 --no-individual     --output-dir zeta_diff

```