import sys
import pandas as pd
import numpy as np
import sklearn
import mlxtend
import scipy
import streamlit
import plotly
import pyarrow
import pyspark

print("========================================")
print("   RETAIL ANALYTICS ENVIRONMENT CHECK   ")
print("========================================")
print(f"Python       : {sys.version.split()[0]}")
print(f"Pandas       : {pd.__version__}")
print(f"NumPy        : {np.__version__}")
print(f"Scikit-Learn : {sklearn.__version__}")
print(f"Mlxtend      : {mlxtend.__version__}")
print(f"SciPy        : {scipy.__version__}")
print(f"Streamlit    : {streamlit.__version__}")
print(f"Plotly       : {plotly.__version__}")
print(f"PyArrow      : {pyarrow.__version__}")
print(f"PySpark      : {pyspark.__version__}")
print("========================================")
print("All libraries loaded successfully!")
