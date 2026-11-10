"""Small dense matrix operations for transparent linear-model experiments."""
from __future__ import annotations
from typing import Sequence

def transpose(matrix: Sequence[Sequence[float]]) -> list[list[float]]:
    if not matrix or any(len(row)!=len(matrix[0]) for row in matrix): raise ValueError("rectangular non-empty matrix required")
    return [list(column) for column in zip(*matrix)]

def matmul(left: Sequence[Sequence[float]],right: Sequence[Sequence[float]]) -> list[list[float]]:
    if not left or not right or any(len(row)!=len(left[0]) for row in left) or any(len(row)!=len(right[0]) for row in right): raise ValueError("rectangular matrices required")
    if len(left[0])!=len(right): raise ValueError("matrix dimensions do not align")
    columns=transpose(right)
    return [[sum(float(a)*float(b) for a,b in zip(row,column)) for column in columns] for row in left]

def solve_linear_system(matrix: Sequence[Sequence[float]],vector: Sequence[float],tolerance: float=1e-12) -> list[float]:
    n=len(matrix)
    if n==0 or len(vector)!=n or any(len(row)!=n for row in matrix): raise ValueError("square system required")
    augmented=[[float(value) for value in row]+[float(vector[i])] for i,row in enumerate(matrix)]
    for column in range(n):
        pivot=max(range(column,n),key=lambda row:abs(augmented[row][column]))
        if abs(augmented[pivot][column])<=tolerance: raise ValueError("singular matrix")
        augmented[column],augmented[pivot]=augmented[pivot],augmented[column]
        scale=augmented[column][column]; augmented[column]=[value/scale for value in augmented[column]]
        for row in range(n):
            if row==column: continue
            factor=augmented[row][column]
            augmented[row]=[a-factor*b for a,b in zip(augmented[row],augmented[column])]
    return [augmented[i][-1] for i in range(n)]

def ridge_regression(features: Sequence[Sequence[float]],target: Sequence[float],regularization: float=1.0) -> tuple[float,...]:
    if len(features)!=len(target) or not features or regularization<0: raise ValueError("invalid regression data")
    width=len(features[0])
    if any(len(row)!=width for row in features): raise ValueError("feature width mismatch")
    x=[[1.0]+[float(v) for v in row] for row in features]; xt=transpose(x); gram=matmul(xt,x)
    for i in range(1,len(gram)): gram[i][i]+=regularization
    rhs=[sum(a*float(y) for a,y in zip(column,target)) for column in xt]
    return tuple(solve_linear_system(gram,rhs))
