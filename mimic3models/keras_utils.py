import numpy as np
import metrics

import keras
import keras.backend as K

if K.backend() == 'tensorflow':
    import tensorflow as tf

from keras.layers import Layer, LSTM
from keras.layers.recurrent import _time_distributed_dense

# ===================== METRICS ===================== #                        

class MetricsBinaryFromGenerator(keras.callbacks.Callback):
    
    def __init__(self, train_data_gen, val_data_gen, batch_size=32, verbose=2):
        self.train_data_gen = train_data_gen
        self.val_data_gen = val_data_gen
        self.batch_size = batch_size
        self.verbose = verbose
    
    def on_train_begin(self, logs={}):
        self.train_history = []
        self.val_history = []
    
    def calc_metrics(self, data_gen, history, dataset, logs):
        y_true = []
        predictions = []
        for i in range(data_gen.steps):
            if self.verbose == 1:
                print "\r\tdone {}/{}".format(i, data_gen.steps),
            (x,y) = next(data_gen)
            pred = self.model.predict(x, batch_size=self.batch_size)

            if isinstance(x, list) and len(x) == 2: # deep supervision
                masks = x[1]
                for smask, sy, spred in zip(masks, y, pred): # examples
                    for tm, ty, tp in zip(smask, sy, spred): # timesteps
                        if np.int(tm) == 1:
                            y_true.append(np.int(ty))
                            predictions.append(np.float(tp))
            else:
                y_true += list(y.flatten())
                predictions += list(pred.flatten())
        print "\n"
        
        predictions = np.array(predictions)
        predictions = np.stack([1-predictions, predictions], axis=1)
        ret = metrics.print_metrics_binary(y_true, predictions)
        for k, v in ret.iteritems():
            logs[dataset + '_' + k] = v
        history.append(ret)

    def on_epoch_end(self, epoch, logs={}):
        print "\n==>predicting on train"
        self.calc_metrics(self.train_data_gen, self.train_history, 'train', logs)
        print "\n==>predicting on validation"
        self.calc_metrics(self.val_data_gen, self.val_history, 'val', logs)


class MetricsBinaryFromData(keras.callbacks.Callback):
    
    def __init__(self, train_data, val_data, batch_size=32, verbose=2):
        self.train_data = train_data
        self.val_data = val_data
        self.batch_size = batch_size
        self.verbose = verbose
    
    def on_train_begin(self, logs={}):
        self.train_history = []
        self.val_history = []
    
    def calc_metrics(self, data, history, dataset, logs):
        y_true = []
        predictions = []
        num_examples = len(data[0])
        for i in range(0, num_examples, self.batch_size):
            if self.verbose == 1:
                print "\r\tdone {}/{}".format(i, num_examples),
            (x,y) = (data[0][i:i+self.batch_size], data[1][i:i+self.batch_size])
            if len(y) == 2: # target replication
                y_true += list(y[0].flatten())
            else:
                y_true += list(y.flatten())
            outputs = self.model.predict(x, batch_size=self.batch_size)
            if len(outputs) == 2:
                predictions += list(outputs[0].flatten())
            else:
                predictions += list(outputs.flatten())
        print "\n"
        predictions = np.array(predictions)
        predictions = np.stack([1-predictions, predictions], axis=1)
        ret = metrics.print_metrics_binary(y_true, predictions)
        for k, v in ret.iteritems():
            logs[dataset + '_' + k] = v
        history.append(ret)
        
    def on_epoch_end(self, epoch, logs={}):
        print "\n==>predicting on train"
        self.calc_metrics(self.train_data, self.train_history, 'train', logs)
        print "\n==>predicting on validation"
        self.calc_metrics(self.val_data, self.val_history, 'val', logs)


class MetricsMultilabel(keras.callbacks.Callback):
    
    def __init__(self, train_data_gen, val_data_gen, batch_size=32, verbose=2):
        self.train_data_gen = train_data_gen
        self.val_data_gen = val_data_gen
        self.batch_size = batch_size
        self.verbose = verbose
    
    def on_train_begin(self, logs={}):
        self.train_history = []
        self.val_history = []
    
    def calc_metrics(self, data_gen, history, dataset, logs):
        y_true = []
        predictions = []
        for i in range(data_gen.steps):
            if self.verbose == 1:
                print "\r\tdone {}/{}".format(i, data_gen.steps),
            (x, y) = next(data_gen)
            if len(y) == 2:
                y_true += list(y[0])
            else:
                y_true += list(y)
            outputs = self.model.predict(x, batch_size=self.batch_size)
            if len(outputs) == 2:
                predictions += list(outputs[0])
            else:
                predictions += list(outputs)
        print "\n"
        predictions = np.array(predictions)
        ret = metrics.print_metrics_multilabel(y_true, predictions)
        for k, v in ret.iteritems():
            logs[dataset + '_' + k] = v
        history.append(ret)
    
    def on_epoch_end(self, epoch, logs={}):
        print "\n==>predicting on train"
        self.calc_metrics(self.train_data_gen, self.train_history, 'train', logs)
        print "\n==>predicting on validation"
        self.calc_metrics(self.val_data_gen, self.val_history, 'val', logs)


class MetricsLOS(keras.callbacks.Callback):
    
    def __init__(self, train_data_gen, val_data_gen, partition, batch_size=32, verbose=2):
        self.train_data_gen = train_data_gen
        self.val_data_gen = val_data_gen
        self.batch_size = batch_size
        self.partition = partition
        self.verbose = verbose
    
    def on_train_begin(self, logs={}):
        self.train_history = []
        self.val_history = []
    
    def calc_metrics(self, data_gen, history, dataset, logs):
        y_true = []
        predictions = []
        for i in range(data_gen.steps):
            if self.verbose == 1:
                print "\r\tdone {}/{}".format(i, data_gen.steps),
            (x, y_processed, y) = data_gen.next(return_y_true=True)
            pred = self.model.predict(x, batch_size=self.batch_size)

            if isinstance(x, list) and len(x) == 2: # deep supervision
                masks = x[1]
                for smask, sy, spred in zip(masks, y, pred): # examples
                    for tm, ty, tp in zip(smask, sy, spred): # timesteps
                        if np.int(tm) == 1:
                            y_true.append(np.float(ty))
                            if len(tp) == 1: # none
                                predictions.append(np.float(tp))
                            else: # custom or log
                                predictions.append(tp)
            else:
                if y.shape[-1] == 1:
                    y_true += list(y.flatten())
                    predictions += list(pred.flatten())
                else:
                    y_true += list(y)
                    predictions += list(pred)
        print "\n"

        if self.partition == 'log':
            predictions = [metrics.get_estimate_log(x, 10) for x in predictions]
            ret = metrics.print_metrics_log_bins(y_true, predictions)
        if self.partition == 'custom':
            predictions = [metrics.get_estimate_custom(x, 10) for x in predictions]
            ret = metrics.print_metrics_custom_bins(y_true, predictions)
        if self.partition == 'none':
            ret = metrics.print_metrics_regression(y_true, predictions)
        for k, v in ret.iteritems():
            logs[dataset + '_' + k] = v
        history.append(ret)

    def on_epoch_end(self, epoch, logs={}):
        print "\n==>predicting on train"
        self.calc_metrics(self.train_data_gen, self.train_history, 'train', logs)
        print "\n==>predicting on validation"
        self.calc_metrics(self.val_data_gen, self.val_history, 'val', logs)


class MetricsMultilabel(keras.callbacks.Callback):

    def __init__(self, train_data_gen, val_data_gen, partition, batch_size=32, verbose=2):
        self.train_data_gen = train_data_gen
        self.val_data_gen = val_data_gen
        self.batch_size = batch_size
        self.partition = partition
        self.verbose = verbose

    def on_train_begin(self, logs={}):
        self.train_history = []
        self.val_history = []

    def calc_metrics(self, data_gen, history, dataset, logs):
        ihm_y_true = []
        decomp_y_true = []
        los_y_true = []
        pheno_y_true = []

        ihm_pred = []
        decomp_pred = []
        los_pred = []
        pheno_pred = []

        for i in range(data_gen.steps):
            if self.verbose == 1:
                print "\r\tdone {}/{}".format(i, data_gen.steps),
            (X, y, los_y_reg) = data_gen.next(return_y_true=True)
            outputs = self.model.predict(X, batch_size=self.batch_size)

            ihm_M = X[1]
            decomp_M = X[2]
            los_M = X[3]

            if len(outputs) == 4: # no target replication
                (ihm_p, decomp_p, los_p, pheno_p) = outputs
                (ihm_t, decomp_t, los_t, pheno_t) = y
            else: # target replication
                (ihm_p, _, decomp_p, los_P, pheno_p, _) = outputs
                (ihm_t, _, decomp_t, los_t, pheno_t, _) = y
        
            los_t = los_y_reg # real value not the label

            ## ihm
            for (m, t, p) in zip(ihm_M.flatten(), ihm_t.flatten(), ihm_p.flatten()):
                if np.equal(m, 1):
                    ihm_y_true.append(t)
                    ihm_pred.append(p)

            ## decomp
            for (m, t, p) in zip(decomp_M.flatten(), decomp_t.flatten(), decomp_p.flatten()):
                if np.equal(m, 1):
                    decomp_y_true.append(t)
                    decomp_pred.append(p)

            ## los
            if los_p.shape[-1] == 1: # regression
                for (m, t, p) in zip(los_M.flatten(), los_t.flatten(), los_p.flatten()):
                    if np.equal(m, 1):
                        los_y_true.append(t)
                        los_pred.append(p)
            else: # classification
                for (m, t, p) in zip(los_M.flatten(), los_t.flatten(), los_p.reshape((-1, 10))):
                    if np.equal(m, 1):
                        los_y_true.append(t)
                        los_pred.append(p)

            ## pheno
            for (t, p) in zip(pheno_t.reshape((-1, 25)), pheno_p.reshape((-1, 25))):
                pheno_y_true.append(t)
                pheno_pred.append(p)
        print "\n"

        ## ihm
        print "\n ================= 48h mortality ================"
        ihm_pred = np.array(ihm_pred)
        ihm_pred = np.stack([1-ihm_pred, ihm_pred], axis=1)
        ret = metrics.print_metrics_binary(ihm_y_true, ihm_pred)
        for k, v in ret.iteritems():
            logs[dataset + '_ihm_' + k] = v

        ## decomp
        print "\n ================ decompensation ================"
        decomp_pred = np.array(decomp_pred)
        decomp_pred = np.stack([1-decomp_pred, decomp_pred], axis=1)
        ret = metrics.print_metrics_binary(decomp_y_true, decomp_pred)
        for k, v in ret.iteritems():
            logs[dataset + '_decomp_' + k] = v

        ## los
        print "\n ================ length of stay ================"
        if self.partition == 'log':
            los_pred = [metrics.get_estimate_log(x, 10) for x in los_pred]
            ret = metrics.print_metrics_log_bins(los_y_true, los_pred)
        if self.partition == 'custom':
            los_pred = [metrics.get_estimate_custom(x, 10) for x in los_pred]
            ret = metrics.print_metrics_custom_bins(los_y_true, los_pred)
        if self.partition == 'none':
            ret = metrics.print_metrics_regression(los_y_true, los_pred)
        for k, v in ret.iteritems():
            logs[dataset + '_los_' + k] = v

        ## pheno
        print "\n =================== phenotype =================="
        pheno_pred = np.array(pheno_pred)
        ret = metrics.print_metrics_multilabel(pheno_y_true, pheno_pred)
        for k, v in ret.iteritems():
            logs[dataset + '_pheno_' + k] = v

        history.append(logs)

    def on_epoch_end(self, epoch, logs={}):
        print "\n==>predicting on train"
        self.calc_metrics(self.train_data_gen, self.train_history, 'train', logs)
        print "\n==>predicting on validation"
        self.calc_metrics(self.val_data_gen, self.val_history, 'val', logs)


# ===================== LAYERS ===================== #                        

def softmax(x, axis, mask=None):
    if mask is None:
        mask = K.constant(True)
    mask = K.cast(mask, K.floatx())
    if K.ndim(x) is K.ndim(mask) + 1:
        mask = K.expand_dims(mask)

    m = K.max(x, axis=axis, keepdims=True)
    e = K.exp(x - m) * mask
    s = K.sum(e, axis=axis, keepdims=True)
    s += K.cast(K.cast(s < K.epsilon(), K.floatx()) * K.epsilon(), K.floatx())
    return e / s


def _collect_attention(x, a, mask):
    """
    x is (B, T, D)
    a is (B, T, 1) or (B, T)
    mask is (B, T)
    """
    if K.ndim(a) == 2:
        a = K.expand_dims(a)
    a = softmax(a, axis=1, mask=mask) # (B, T, 1)
    return K.sum(x * a, axis=1) # (B, D)


class CollectAttetion(Layer):
    """ Collect attention on 3D tensor with softmax and summation
        Masking is disabled after this layer
    """
    def __init__(self, **kwargs):
        self.supports_masking = True
        super(CollectAttetion, self).__init__(**kwargs)

    def call(self, inputs, mask=None):
        x = inputs[0]
        a = inputs[1]
        # mask has 2 components, both are the same
        return _collect_attention(x, a, mask[0])
    
    def compute_output_shape(self, input_shape):
        return input_shape[0][0], input_shape[0][2]

    def compute_mask(self, input, input_mask=None):
        return None


class Slice(Layer):
    """ Slice 3D tensor by taking x[:, :, indices]
    """
    def __init__(self, indices, **kwargs):
        self.supports_masking = True
        self.indices = indices
        super(Slice, self).__init__(**kwargs)

    def call(self, x, mask=None):
        if K.backend() == 'tensorflow':
            xt = tf.transpose(x, perm=(2, 0 ,1))
            gt = tf.gather(xt, self.indices)
            return tf.transpose(gt, perm=(1, 2, 0))
        return x[:, :, self.indices]

    def compute_output_shape(self, input_shape):
        return (input_shape[0], input_shape[1], len(self.indices))

    def compute_mask(self, input, input_mask=None):
        return input_mask

    def get_config(self):
        return {'indices': self.indices}


class GetTimestep(Layer):
    """ Takes 3D tensor and returns x[:, pos, :]
    """
    def __init__(self, pos=-1, **kwargs):
        self.pos = pos
        self.supports_masking = True
        super(LastTimestep, self).__init__(**kwargs)

    def call(self, x, mask=None):
        # TODO: test on tensorflow
        return x[:, self.pos, :]

    def compute_output_shape(self, input_shape):
        return (input_shape[0], input_shape[2])

    def compute_mask(self, input, input_mask=None):
        return None

    def get_config(self):
        return {'pos': self.pos}

LastTimestep = GetTimestep


class ExtendMask(Layer):
    """ Inputs:      [X, M]
        Output:      X
        Output_mask: M
    """
    def __init__(self, **kwargs):
        self.supports_masking = True
        super(ExtendMask, self).__init__(**kwargs)

    def call(self, x, mask=None):
        return x[0]

    def compute_output_shape(self, input_shape):
        return input_shape[0]

    def compute_mask(self, input, input_mask=None):
        return input[1]
