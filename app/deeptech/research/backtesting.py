"""Rolling-origin backtesting for chronological forecasting experiments."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Sequence
from .forecasting import mean_absolute_error, root_mean_squared_error

@dataclass(frozen=True, slots=True)
class BacktestFold:
    origin: int
    horizon: int
    mae: float
    rmse: float
    actual: tuple[float,...]
    predicted: tuple[float,...]

class RollingOriginBacktest:
    def run(self,values: Sequence[float],forecaster: Callable[[Sequence[float],int],Sequence[float]],initial_window: int,horizon: int=1,step: int=1) -> tuple[BacktestFold,...]:
        data=list(map(float,values))
        if initial_window<2 or horizon<1 or step<1 or initial_window+horizon>len(data): raise ValueError("invalid backtest dimensions")
        folds=[]
        for origin in range(initial_window,len(data)-horizon+1,step):
            history=data[:origin]; actual=tuple(data[origin:origin+horizon]); predicted=tuple(map(float,forecaster(history,horizon)))
            if len(predicted)!=horizon: raise ValueError("forecaster returned wrong horizon")
            folds.append(BacktestFold(origin,horizon,mean_absolute_error(actual,predicted),root_mean_squared_error(actual,predicted),actual,predicted))
        return tuple(folds)
    def aggregate(self,folds: Sequence[BacktestFold]) -> dict:
        if not folds: raise ValueError("backtest folds required")
        return {"folds":len(folds),"mean_mae":sum(f.mae for f in folds)/len(folds),"mean_rmse":sum(f.rmse for f in folds)/len(folds),"origins":[f.origin for f in folds]}
