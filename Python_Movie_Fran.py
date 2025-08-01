# In this code I use a cross validated Ridge regression of a GLM with a Poisson Distribution

import numpy as np
import pandas as pd
import sqlite3 as db
import numpy as np
import sklearn.linear_model as lm
from sklearn.feature_selection import RFECV
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import make_scorer
from sklearn.model_selection import GridSearchCV

Movie_Revenue = pd.read_csv("https://drive.google.com/uc?export=download&id=1uo6ixKfZHxwu1egSpq8jB9RFlDHGGOWT")
Ref_Franchise = pd.read_csv("https://drive.google.com/uc?export=download&id=1UTNbUkAKdSw6OPT2AGstS0yw1xKxLFKq")
Ref_Genre = pd.read_csv("https://drive.google.com/uc?export=download&id=1kTAF4MKMvMIATgrQb5xgyl_W_mMUBI6t")
Ref_Director = pd.read_csv("https://drive.google.com/uc?export=download&id=1bBUq0DYkzQ3A5rzfZGjHCw-4TFcCctoB")
Ref_Cast = pd.read_csv("https://drive.google.com/uc?export=download&id=1ZVyCGz7uZOWYuqKX2oNzO2LIrTook6bL")

Movie_Revenue['ReleaseDate'] = pd.to_datetime(Movie_Revenue['ReleaseDate'], format='%m/%d/%Y')
Movie_Revenue = Movie_Revenue.rename(columns={'Lifetime Gross': 'Lifetime_Gross'})

conn = db.connect("Movie.db")
Movie_Revenue.to_sql('Movie_Revenue', conn, if_exists='replace', index=False)
Ref_Franchise.to_sql('Ref_Franchise', conn, if_exists='replace', index=False)
Ref_Genre.to_sql('Ref_Genre', conn, if_exists='replace', index=False)
Ref_Director.to_sql('Ref_Director', conn, if_exists='replace', index=False)
Ref_Cast.to_sql('Ref_Cast', conn, if_exists='replace', index=False)

query = '''
SELECT Movie_Revenue.MovieID,
Ref_Franchise.FranchiseId,
Movie_Revenue.Title,
Movie_Revenue.Lifetime_Gross,
Movie_Revenue.Year,
Movie_Revenue.Rating,
Movie_Revenue.Runtime,
Movie_Revenue.Budget,
Ref_Franchise.FranchiseName
FROM Movie_Revenue
LEFT JOIN Ref_Franchise ON (Movie_Revenue.FranchiseID=Ref_Franchise.FranchiseId)
'''
Fran_data = pd.read_sql_query(query, conn)
Fran_data = Fran_data.sort_values(by='Budget')
conn.close()

Fran_data.head()

# Notice the right-skewed distribution
Fran_data['Lifetime_Gross'].plot.density()

#Train test split with a random draw of index numbers stratitfied by Franchise
X_test = Fran_data.groupby('FranchiseName').sample(n=2, random_state=123)
print(len(X_test))
X_train = Fran_data[~Fran_data.index.isin(X_test.index)]
train_X = X_train.copy()
print(len(X_train))
y = Fran_data['Lifetime_Gross'].to_numpy()
y_test = y[X_test.index]
print(len(y_test))
mask = np.ones(y.shape, dtype=bool)
mask[X_test.index] = False
y_train = y[mask]
print(len(y_train))

X_dummies = pd.get_dummies(X_train[['Rating', 'FranchiseName']])
X_dummies.reset_index(drop=True,inplace=True)
scaler = StandardScaler()
X_train_sub = X_train[['Year', 'Runtime', 'Budget']]
X_train = scaler.fit_transform(X_train_sub)
X_train = pd.DataFrame(X_train, columns=X_train_sub.columns)
X_train = pd.concat([X_train,X_dummies], axis=1)
X_train.head()

X_dummies = pd.get_dummies(X_test[['Rating', 'FranchiseName']])
X_dummies.reset_index(drop=True,inplace=True)
scaler = StandardScaler()
X_test_sub = X_test[['Year', 'Runtime', 'Budget']]
X_test = scaler.fit_transform(X_test_sub)
X_test = pd.DataFrame(X_test, columns=X_test_sub.columns)
X_test = pd.concat([X_test,X_dummies], axis=1)
X_test.head()

k = len(X_train)-1
param_grid = {'alpha': np.arange(8.5e7,9e7,1e5)}
grid_cv = GridSearchCV(lm.PoissonRegressor(), param_grid, cv=k, scoring='neg_mean_poisson_deviance')
fit = grid_cv.fit(X_train, y_train)
fit.best_estimator_
#alpha parameter (l2_wt for Ridge regression to prevent overfitting) was huge because the y values remained in the same units while the x-values were standardized (that could easily be solved but I kept it that way for easier graph construction)

p_lm = lm.PoissonRegressor(alpha=86500000.0)
fit = p_lm.fit(X_train, y_train)
print('Training Deviance Explained',fit.score(X_train, y_train))
# 44% of deviance explained from the training model

test_yhat = p_lm.predict(X_test)
print('Test Dataset Coefficient of Variation',np.sqrt(sum((y_test-test_yhat)**2)/len(y_test))/np.mean(y_test))
# 0.66 normalized root mean square error on the predictions of the test data

# create data to isolate the effect of movie budget on revenue
scaler = StandardScaler()
year_mean = np.mean(scaler.fit_transform(Fran_data[['Year']]))
run_mean = np.mean(scaler.fit_transform(Fran_data[['Runtime']]))
newdata = pd.DataFrame({'Year': year_mean, 'Runtime': run_mean, 'Budget': np.arange(-3,3,0.1), 'Rating_PG':0, 'Rating_PG-13':1,
                        'FranchiseName_Jurassic Park':0, 'FranchiseName_MCU':1, 'FranchiseName_Middle Earth':0, 'FranchiseName_Star Wars':0, 'FranchiseName_Wizarding World':0})
y_hat = p_lm.predict(newdata)

Budget_stand = pd.DataFrame({'Budget':scaler.fit_transform(Fran_data[['Budget']]).flatten()})
std_Xtrain = np.std(train_X['Budget'])
mean_Xtrain = np.mean(train_X['Budget'])

from bokeh.plotting import figure, output_notebook, show
output_notebook()

fig = figure()
fig.scatter((Budget_stand['Budget']*std_Xtrain+mean_Xtrain)/1e6, Fran_data['Lifetime_Gross']/1e6, size=5, color="navy", alpha=0.5)
fig.line((newdata['Budget']*std_Xtrain+mean_Xtrain)/1e6, y_hat/1e6, line_width=2, color="red")
fig.xaxis.axis_label = "Movie Budget (millions of dollars)"
fig.yaxis.axis_label = "Movie Lifetime Revenue (millions of dollars)"
show(fig)





