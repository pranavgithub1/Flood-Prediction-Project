from datetime import datetime
from math import sqrt
import numpy as np
from keras.regularizers import l2
from numpy import concatenate
from matplotlib import pyplot
import pandas as pd
from pandas import DataFrame
from pandas import read_csv,read_table
from pandas import concat
from sklearn.preprocessing import MinMaxScaler
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_squared_error
from keras.models import Sequential
from keras.layers import Dense, GRU
from keras.layers import LSTM
from keras.metrics import accuracy
def parse(x):
    return datetime.strptime(x, '%Y %m %d %H')

def series_to_supervised(data, n_in=1, n_out=1, dropnan=True):
	n_vars = 1 if type(data) is list else data.shape[1]
	df = DataFrame(data)
	cols, names = list(), list()
	# input sequence (t-n, ... t-1)
	for i in range(n_in, 0, -1):
		cols.append(df.shift(i))
		names += [('var%d(t-%d)' % (j+1, i)) for j in range(n_vars)]
	# forecast sequence (t, t+1, ... t+n)
	for i in range(0, n_out):
		cols.append(df.shift(-i))
		if i == 0:
			names += [('var%d(t)' % (j+1)) for j in range(n_vars)]
		else:
			names += [('var%d(t+%d)' % (j+1, i)) for j in range(n_vars)]
	# put it all together
	agg = concat(cols, axis=1)
	agg.columns = names
	# drop rows with NaN values
	if dropnan:
		agg.dropna(inplace=True)
	return agg


metObs = read_table(r"C:\MLProject\CAMELS_dataset\Hydrometeorological_Time_Series\basin_dataset_public_v1p2\basin_mean_forcing\daymet\08\07375000_lump_cida_forcing_leap.txt",header=3,sep="\s+|\t+",parse_dates=[['Year','Mnth','Day','Hr']],date_parser=parse,index_col=0)
flowObs = read_table(r"C:\MLProject\CAMELS_dataset\Hydrometeorological_Time_Series\basin_dataset_public_v1p2\usgs_streamflow\08\07375000_streamflow_qc.txt",sep="\s+|\t+",names=['GAGEID','Year','Mnth','Day','streamflow(cfs)','QC_flag'])
metObs.index.name = "date"
metObs["streamflow(cfs)"] = flowObs["streamflow(cfs)"].values
#metObs["streamflow(cfs)"].replace(to_replace=-999.0, value=0)
metObs = metObs[metObs["streamflow(cfs)"]!=-999.0]
#print(metObs.head())
metObs = metObs[['streamflow(cfs)', 'dayl(s)', 'prcp(mm/day)', 'srad(W/m2)', 'swe(mm)','tmax(C)', 'tmin(C)', 'vp(Pa)']]
#print(metObs.head())
#print(flowObs)
#flowObs.drop(['GAGEID','Year','Mnth','Day','QC_flag'],axis=1,inplace=True)
#metObs["streamflow(cfs)"] = flowObs.values
metObs.to_csv('allData.csv')
#print(metObs.columns)
#pyplot.plot(metObs['streamflow(cfs)'],label='Q')
#pyplot.show()
# SERIES TO SUPERVISED
cleaned = read_csv('allData.csv', index_col=0)
cleaned.drop(cleaned.columns[[1, 3, 4, 5, 6, 7]], axis=1, inplace=True)
# load dataset
NNtype = 'LSTM'
div = 5
batch_size = 75
epochs = [10,20,30,40,50,60,70,80,90,100]
input_neurons = 100
output_activation = 'linear'
loss = 'mae'
optimizer = 'adam'
num_runs = 30
runsList = [i+1 for i in range(num_runs)]
ticksList = [runsList[i-1] for i in [div+(div*i) for i in range(int(num_runs/div))]]
ticksList.insert(0,1)
titletxt = "{} Root Mean Squared Error (RMSE)".format(NNtype)
allRMSE = []
txt = 'batch_size: {}, epochs: {}, input neurons: {}, output activation: {}, loss: {}, optimizer: {}, number of runs: {}'.format(batch_size,epochs,input_neurons,output_activation,loss,optimizer,num_runs)
for e in epochs:
	rmseList = []
	for i in range(num_runs):
		values = cleaned.values
		values = values.astype('float32')
		scaler = MinMaxScaler(feature_range=(0,1))
		scaled = scaler.fit_transform(values)
		reframed = series_to_supervised(scaled,1,1)
		tempReframed = reframed
		tempReframed.drop(reframed.columns[[3]],axis=1,inplace=True)
		values = tempReframed.values
		n_train_days = 15*365
		train = values[:n_train_days, :]
		test = values[n_train_days:, :]

		# split into input and output
		train_X, train_y = train[:,:-1], train[:, -1]
		test_X, test_y = test[:,:-1], test[:,-1]
		# reshape input to be 3D
		train_X = train_X.reshape((train_X.shape[0], 1, train_X.shape[1]))
		test_X = test_X.reshape((test_X.shape[0], 1, test_X.shape[1]))
		#CREATE LSTM
		# design network
		model = Sequential()
		model.add(LSTM(input_neurons, input_shape=(train_X.shape[1], train_X.shape[2]),return_sequences=True))
		model.add(LSTM(input_neurons, input_shape=(train_X.shape[1], train_X.shape[2]),return_sequences=False))
		model.add(Dense(1,activation=output_activation))
		model.compile(loss=loss, optimizer=optimizer)
		# fit network
		pyplot.figure(1)
		history = model.fit(train_X, train_y, epochs=e, batch_size=batch_size, validation_data=(test_X, test_y), verbose=2, shuffle=False)
		yhat = model.predict(test_X)
		test_X = test_X.reshape((test_X.shape[0], test_X.shape[2]))
		# invert scaling for forecast
		tempTest_X = test_X[:, 0]
		tempTest_X = tempTest_X.reshape(len(tempTest_X), 1)
		print("first concat shape (yhat,tempTest_X)", yhat.shape,tempTest_X.shape)
		inv_yhat = concatenate((yhat, tempTest_X), axis=1)
		print("inv_yhat shape after first concat: ",inv_yhat.shape)
		inv_yhat = scaler.inverse_transform(inv_yhat)
		inv_yhat = inv_yhat[:, 0]
		# invert scaling for actual
		test_y = test_y.reshape((len(test_y), 1))
		print("second concat shape (test_y,test_X): ", test_y.shape, test_X.shape)
		inv_y = concatenate((test_y, tempTest_X), axis=1)
		print("inv_y shape after second concat: ",inv_y.shape)
		inv_y = scaler.inverse_transform(inv_y)
		inv_y = inv_y[:, 0]
		# calculate RMSE
		rmse = sqrt(mean_squared_error(inv_y, inv_yhat))
		print(rmse)
		rmseList.append(rmse)
	allRMSE.append(rmseList)
fig = pyplot.figure(figsize=(6,5))
axes = fig.add_axes([0.2,0.2,0.7,0.7])
axes.plot(runsList,rmseList,color='tab:blue',marker='o')
pyplot.ylim((200,350))
pyplot.xticks(ticksList)
pyplot.xlabel("Run Number")
pyplot.ylabel("RMSE")
fig.suptitle(titletxt,fontsize=16)
pyplot.figtext(0.5,0.01,txt,wrap=True,horizontalalignment='center',fontsize=12)
pyplot.savefig("MultipleRunsLoss.png")


"""
# make a prediction
yhat = model.predict(test_X)
print("yhat shape: ",yhat.shape)
print(yhat[:3,:])
test_X = test_X.reshape((test_X.shape[0], test_X.shape[2]))
print("test_X shape: ",test_X.shape)
print("test_X[:,0] shape: ",test_X[:,0].shape)
# invert scaling for forecast
tempTest_X = test_X[:,0]
tempTest_X = tempTest_X.reshape(len(tempTest_X),1)
print("tempTest_X shape: ",tempTest_X.shape)
inv_yhat = concatenate((yhat, tempTest_X), axis=1)
print("inv_yhat shape: ",inv_yhat.shape)
print(inv_yhat[:3,:])
inv_yhat = scaler.inverse_transform(inv_yhat)
inv_yhat = inv_yhat[:,0]
# invert scaling for actual
test_y = test_y.reshape((len(test_y), 1))
print("line 156 concat shape (test_y,test_X): ",test_y.shape,test_X.shape)
inv_y = concatenate((test_y, tempTest_X), axis=1)
inv_y = scaler.inverse_transform(inv_y)
inv_y = inv_y[:,0]
# calculate RMSE
rmse = sqrt(mean_squared_error(inv_y, inv_yhat))
accuracy = accuracy(inv_y, inv_yhat)
print('Test RMSE: %.3f' % rmse)
print("inv_y,inv_yhat shape: ",inv_y.shape,inv_yhat.shape)
temp1 = inv_y
temp2 = inv_yhat

temp1.reshape(inv_y.shape[0],1)
temp2.reshape(inv_yhat.shape[0],1)
print("temp1,temp2 shape: ",temp1.shape,temp2.shape)
streamflow_combined = concatenate((temp1,temp2),axis=1)
print(streamflow_combined[:5,:])

streamflow_combined = np.column_stack((temp1,temp2))
streamflow_combined = pd.DataFrame(streamflow_combined)
streamflow_combined.columns = ['inv_y','inv_yhat']
print(streamflow_combined.head())
streamflow_combined.to_csv("streamflow_combined.csv")

pyplot.figure(2)
pyplot.plot(inv_y, label='observed')
pyplot.plot(inv_yhat, label='predicted')
pyplot.legend()
pyplot.savefig("Time_series.png")
pyplot.show()



pyplot.figure(3)
pyplot.scatter(inv_y,inv_yhat,facecolors='none',edgecolors='k')
xmin,xmax = 0,14000
pyplot.title("Observed vs Predicted Streamflow (cfs) Scatterplot")
pyplot.axis([xmin,xmax,xmin,xmax])
pyplot.ylabel('Predicted Streamflow (cfs)')
pyplot.xlabel('Observed Streamflow (cfs)')
pyplot.plot([xmin,xmax], [xmin,xmax], 'r--')
pyplot.savefig("Q_Scatter.png")
pyplot.show()


err_y = inv_yhat - inv_y
print("Err min,max: ",min(err_y),max(err_y))
print("Err shape: ",err_y.shape)
pyplot.figure(4)
pyplot.title("Error (cfs) Histogram")
pyplot.hist(err_y,100)
#pyplot.xlim(3000)
pyplot.xlim((-1000,1000))
pyplot.plot([0,0],[0,8000], 'r--')
neg_err = (sum(x<0 for x in err_y)/err_y.shape[0])*100
pos_err = (sum(x>0 for x in err_y)/err_y.shape[0])*100
zero_err = (sum(x==0 for x in err_y)/err_y.shape[0])*100
#pyplot.text(x=0,y=8500,s="% Below 0: "+str(neg_err))
#pyplot.text(x=0,y=8000,s="% Above 0: "+str(pos_err))
#pyplot.text(x=0,y=7500,s="% = 0: "+str(zero_err))
pyplot.savefig("Err_Histogram.png")
pyplot.show()
"""

