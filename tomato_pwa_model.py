import numpy as np
import statsmodels.api as sm
from scipy import linalg, optimize
from sklearn.svm import SVC

H_0 = 62.9
H_plusinf = 43.1
H_minusinf = 124
k_ref = 0.0019
E_a = 170.604
T_ref = 288.15
Rg = 0.008314

T_min, T_max = 278, 298
H_min, H_max = 40, 65
Enz_min, Enz_max = 90, 110


def k_rate(T):
    return k_ref*np.exp((E_a/Rg)*(1/T_ref-1/T))

def f_H(T,H,Enz):
    return -k_rate(T)*H*Enz

def f_Enz(T,H,Enz):
    return k_rate(T)*H*Enz


n = 3
N = 200
c = 5
s = 3

# row vector(1-dim array)
T = np.random.randint(T_min,T_max,(N,))
H = np.random.randint(H_min,H_max,(N,))
Enz = np.random.randint(Enz_min,Enz_max,(N,))

# X : n×N dimension matrix, y : N dimension row vector(1-dim array)
X = np.array([T,H,Enz])
y_H = f_H(T,H,Enz)
y_Enz = f_Enz(T,H,Enz)

# Norm  :N×N dimension matrix, Norm_sort : N×N dimension matrix, C : N×c dimension matrix
Norm = np.empty((X.shape[1], X.shape[1]))
for i in range(X.shape[1]):
    for j in range(X.shape[1]):
        Norm[i, j] = np.linalg.norm(X[:, i] - X[:,j])
Norm_sort = np.argsort(Norm, axis=1)
C = Norm_sort[:, 0:c]

# Xc : N×n×c dimension matrix, T_c,H_c,Enz_c : N×c dimension matrix, Yc : N×c×1 dimension matrix
Xc = np.empty((C.shape[0], X.shape[0], C.shape[1]))
for i in range(Xc.shape[0]):
    for j in range(Xc.shape[2]):
        Xc[i, :, j] = X[:, C[i, j]]
T_c = Xc[:, 0, :]
H_c = Xc[:, 1, :]
Enz_c = Xc[:, 2, :]

yc_H = f_H(T_c,H_c,Enz_c)
Yc_H = yc_H[:, :, np.newaxis]
yc_Enz = f_Enz(T_c,H_c,Enz_c)
Yc_Enz = yc_Enz[:, :, np.newaxis]

# Phi : N×c×(n+1) dimension matrix, (Phi)'×Phi : N×2×2 dimension matrix, inverse matrix of phi : N×c×c dimension matrix, theta_ls : N×(n+1)×1 dimension matrix
one = np.ones((Xc.shape[0], 1, Xc.shape[2]))
Phi_T = np.concatenate((Xc, one), axis=1)
Phi = Phi_T.transpose(0, 2, 1)
phi = Phi_T @ Phi
inv_phi = np.linalg.inv(phi)
PHI = inv_phi @ Phi_T
Theta_ls_H = PHI @ Yc_H
Theta_ls_Enz = PHI @ Yc_Enz

# SSR : N dimension vector, m : N×n dimension row vector(1-dim array), V : N×(n+1)×(n+1) dimension matrix, Q : N×n×n dimension matrix, eps : feature vector(N×(2n+1) dimension matrix), R : N×(2n+1)×(2n+1) matrix, w : N dimension vector (1dim-array)
eye = np.stack(([np.eye(Xc.shape[2])]*Xc.shape[0]), axis = 0)
SSR_H = Yc_H.transpose(0, 2, 1) @ (eye - (Phi @ PHI)) @ Yc_H
SSR_Enz = Yc_Enz.transpose(0, 2, 1) @ (eye - (Phi @ PHI)) @ Yc_Enz
m = np.sum(Xc, axis=2)/c
V_H = (SSR_H/(c-n-1)) * inv_phi
V_Enz = (SSR_Enz/(c-n-1)) * inv_phi
Q = (Xc-m[:,:,np.newaxis]) @ (Xc-m[:,:,np.newaxis]).transpose(0,2,1)
theta_ls_H = Theta_ls_H.transpose(0, 2, 1)
theta_ls_Enz = Theta_ls_Enz.transpose(0, 2, 1)
eps_H = np.empty((Xc.shape[0], 2*Xc.shape[1]+1))
eps_Enz = np.empty((Xc.shape[0], 2*Xc.shape[1]+1))
for i in range(Xc.shape[0]):
    eps_H[i, :] = np.concatenate((theta_ls_H[i, :, :].flatten(),m[i, :]), axis = 0)
    eps_Enz[i, :] = np.concatenate((theta_ls_Enz[i, :, :].flatten(),m[i, :]), axis = 0)
Zero_upper = np.zeros((V_H.shape[0], V_H.shape[1], Q.shape[2]))
Zero_lower = np.zeros((Q.shape[0], Q.shape[1], V_H.shape[2]))
Upper_H = np.concatenate((V_H, Zero_upper), axis=2)
Upper_Enz = np.concatenate((V_Enz, Zero_upper), axis=2)
Lower = np.concatenate((Zero_lower, Q), axis=2)
R_H = np.concatenate((Upper_H,Lower), axis=1)
R_Enz = np.concatenate((Upper_Enz,Lower), axis=1)
pai = np.power(2*np.pi, 2*n+1)
det_R_H = np.linalg.det(R_H)
det_R_Enz = np.linalg.det(R_Enz)
re_w_H = np.sqrt(pai*det_R_H)
re_w_Enz = np.sqrt(pai*det_R_Enz)
w_H = 1/re_w_H
w_Enz = 1/re_w_Enz


class FMeans_pp:
    def __init__(self, n_clusters, max_iter = 1000, random_seed = 0):
        self.n_clusters = n_clusters
        self.max_iter = max_iter
        self.random_state = np.random.RandomState(random_seed)

    def fit(self, X, R):
        #ランダムに最初のクラスタ点を決定
        # X : N×(2n+1) matrix, R : N×(2n+1)×(2n+1) matrix(array), tmp : scalar
        tmp = np.random.choice(np.array(range(X.shape[0])))
        first_cluster = X[tmp]
        first_cluster = first_cluster[np.newaxis,:]
        Rinv = np.linalg.inv(R)
        #print('Rinv:', Rinv.shape)

        #最初のクラスタ点とそれ以外のデータ点との行列ノルムの2乗を計算し、それぞれをその総和で割る
        #∥X-first_cluster∥_Rinv^2 = <X-first_cluster, Rinv(x-first_cluster)>
        #X-first_cluster : N×(2n+1) matrix, Rinv(x-first_cluster) : N×(2n+1)×1 matrix(array)
        left_vec = X - first_cluster
        right_vec = Rinv @ left_vec[:,:,np.newaxis]
        #norm_m = left_vec[:,np.newaxis,:] @ right_vec
        #dist_p = np.diagonal(norm_m, axis1 = 1, axis2 = 2)
        # p : N dimension vector(1-dim array)
        p = ((left_vec[:,np.newaxis,:] @ right_vec) / (left_vec[:,np.newaxis,:] @ right_vec).sum()).reshape(X.shape[0],)
        #print('p:', p)
        #print('norm:', left_vec[:,np.newaxis,:] @ right_vec)

        #最初のクラスタ点とそれ以外のデータ点との距離の2乗を計算し、それぞれをその総和で割る
        # p : N dimension vector(1-dim array)
        #p = ((X - first_cluster)**2).sum(axis = 1) / ((X - first_cluster)**2).sum()

        r =  np.random.choice(np.array(range(X.shape[0])), size = 1, replace = False, p = p)

        first_cluster = np.r_[first_cluster ,X[r]]
        #print('first_cluster:', first_cluster)

        #分割するクラスター数が3個以上の場合
        if self.n_clusters >= 3:
            #指定の数のクラスタ点を指定できるまで繰り返し
            while first_cluster.shape[0] < self.n_clusters:
                #各クラスター点と各データポイントとの行列ノルムの2乗を算出
                #dist_f : N×s matrix
                left_v = (X[:, :, np.newaxis] - first_cluster.T[np.newaxis, :, :]).transpose(0, 2, 1)
                right_v = Rinv @ (X[:, :, np.newaxis] - first_cluster.T[np.newaxis, :, :])
                norm_m = left_v @ right_v
                dist_f = np.diagonal(norm_m, axis1 = 1, axis2 =2)
                #print('dist_f(pre):', dist_f)
                dist_f.flags.writeable = True
                #各クラスター点と各データポイントとの距離の2乗を算出
                #dist_f = ((X[:, :, np.newaxis] - first_cluster.T[np.newaxis, :, :])**2).sum(axis = 1)
                #最も距離の近いクラスター点はどれか導出
                f_argmin = dist_f.argmin(axis = 1)
                #最も距離の近いクラスター点と各データポイントとの行列ノルムの2乗を導出
                #属しないクラスター点との距離を0にする
                for i in range(dist_f.shape[1]):
                    dist_f.T[i][f_argmin != i] = 0
                #print('dist_f:', dist_f)

                #新しいクラスタ点を確率的に導出
                pp = dist_f.sum(axis = 1) / dist_f.sum()

                rr = np.random.choice(np.array(range(X.shape[0])), size = 1, replace = False, p = pp)
                #新しいクラスター点を初期値として加える
                first_cluster = np.r_[first_cluster ,X[rr]]
        print('first_cluster:', first_cluster)

        #最初のラベルづけを行う
        left = (X[:, :, np.newaxis] - first_cluster.T[np.newaxis, :, :]).transpose(0, 2, 1)
        right = Rinv @ (X[:, :, np.newaxis] - first_cluster.T[np.newaxis, :, :])
        norm = left @ right
        dist = np.diagonal(norm, axis1 = 1, axis2 =2)
        #dist = (((X[:, :, np.newaxis] - first_cluster.T[np.newaxis, :, :]) ** 2).sum(axis = 1))
        print('dist(first):', dist)
        self.labels_ = dist.argmin(axis = 1)
        print('labels(first):', self.labels_)
        labels_prev = np.zeros(X.shape[0])
        count = 0
        self.cluster_centers_ = np.zeros((self.n_clusters, X.shape[1]))

        #各データポイントが属しているクラスターが変化しなくなった、又は一定回数の繰り返しを越した場合は終了
        while (not (self.labels_ == labels_prev).all() and count < self.max_iter):
            #update the centers of the cluster
            for i in range(self.n_clusters):
                XX = X[self.labels_ == i, :]
                RR = Rinv[self.labels_ == i, :, :]
                print('RR:', RR.shape)
                RRinv = np.linalg.inv(RR.sum(axis=0))
                self.cluster_centers_[i, :] = (RRinv @ ((RR @ XX[:,:,np.newaxis]).sum(axis=0))).T

            print('cluster_centers:', self.cluster_centers_)
            #その時点での各クラスターの重心を計算する
            #for i in range(self.n_clusters):
            #   XX = X[self.labels_ == i, :]
            #  self.cluster_centers_[i, :] = XX.mean(axis = 0)
            #各データポイントと各クラスター中心間の行列ノルムを総当たりで計算する
            # dist : N×s dimension matrix
            Left_v = (X[:,:,np.newaxis] - self.cluster_centers_.T[np.newaxis,:,:]).transpose(0,2,1)
            Right_v = Rinv @ (X[:,:,np.newaxis] - self.cluster_centers_.T[np.newaxis,:,:])
            Norm = Left_v @ Right_v
            dist = np.diagonal(Norm, axis1 = 1, axis2 =2)
            print('dist:', dist)
            #1つ前のクラスターラベルを覚えておく。1つ前のラベルとラベルが変化しなければプログラムは終了する。
            labels_prev = self.labels_
            #再計算した結果、最も距離の近いクラスターのラベルを割り振る
            self.labels_ = dist.argmin(axis = 1)
            print('labels:', self.labels_)
            count += 1
            self.count = count
            print('count:', self.count)

    def predict(self, X):
        dist = ((X[:, :, np.newaxis] - self.cluster_centers_.T[np.newaxis, :, :]) ** 2).sum(axis = 1)
        labels = dist.argmin(axis = 1)
        return labels



model_H =  FMeans_pp(s)
model_Enz =  FMeans_pp(s)
model_H.fit(eps_H, R_H)
model_Enz.fit(eps_Enz, R_Enz)
print('f_H(t): ', model_H.labels_.shape)
print('f_Enz(t): ', model_Enz.labels_.shape)


#-----------------------------------f_H(t)の線形回帰-----------------------------------------------------#
print('----------------------------------------------------------------------------------------')
print('-----------------------------------f_H(t)の線形回帰--------------------------------------')
print('----------------------------------------------------------------------------------------')

model = FMeans_pp(s)
model.fit(eps_H, R_H)

Xr0 = Xc[model.labels_ == 0,:,:]
wr0 = w_H[model.labels_ == 0]
#print('wr0:', wr0.shape)
X0 = Xr0[0,:,:]
w0 = [wr0[0]]*c
for i in range(Xr0.shape[0]-1):
    i += 1
    X0 = np.c_[X0, Xr0[i,:,:]]
    w0 = np.r_[w0, [wr0[i]]*c]
#print('X0:', X0.shape)
#print('w0:', w0.shape)
T0 = X0[0,:]
H0 = X0[1,:]
Enz0 = X0[2,:]
y0 = f_H(T0, H0, Enz0)

Xr1 = Xc[model.labels_ == 1,:,:]
wr1 = w_H[model.labels_ == 1]
#print('wr1:', wr1.shape)
X1 = Xr1[0,:,:]
w1 = [wr1[0]]*c
for i in range(Xr1.shape[0]-1):
    i += 1
    X1 = np.c_[X1, Xr1[i,:,:]]
    w1 = np.r_[w1, [wr1[i]]*c]
#print('X1:', X1.shape)
#print('w1:', w1.shape)
T1 = X1[0,:]
H1 = X1[1,:]
Enz1 = X1[2,:]
y1 = f_H(T1, H1, Enz1)

Xr2 = Xc[model.labels_ == 2,:,:]
wr2 = w_H[model.labels_ == 2]
#print('wr2:', wr2.shape)
X2 = Xr2[0,:,:]
w2 = [wr2[0]]*c
for i in range(Xr2.shape[0]-1):
    i += 1
    X2 = np.c_[X2, Xr2[i,:,:]]
    w2 = np.r_[w2, [wr2[i]]*c]
#print('X2:', X2.shape)
#print('w2:', w2.shape)
T2 = X2[0,:]
H2 = X2[1,:]
Enz2 = X2[2,:]
y2 = f_H(T2, H2, Enz2)

F = [X0, X1, X2]
L = [y0, y1, y2]
W = [w0, w1, w2]

theta = np.empty((s, n+1))

for i in range(s):
    Fe = sm.add_constant(F[i].T)
    mod_wls = sm.WLS(L[i], Fe, weights=W[i])
    res_wls = mod_wls.fit()
    theta[i,:] = res_wls.params

print('------------------------------------------------------------------------------------------------------------------')
print('[y切片, Tの係数, Hの係数, Enzの係数]:\n', theta)


X_features = np.concatenate([X0, X1, X2], 1)
X_labels = np.concatenate((np.array([0]*X0.shape[1]), np.array([1]*X1.shape[1]), np.array([2]*X2.shape[1])), axis = 0)
clf = SVC(kernel='linear', decision_function_shape='ovo')
clf.fit(X_features.T, X_labels)
Norm_SV_ID = clf.decision_function(clf.support_vectors_)
Num_SV = clf.n_support_

for i in range(s):
    print('Number of label %d : %d' % (i, F[i].shape[1]))

print('X_features:', X_features.shape)
print('X_labels:', X_labels.shape)
print('coef_ID function(T,H,Enz):\n', clf.coef_)
print('intercept_ID function(S):\n', clf.intercept_)
#print('support_index:\n', clf.support_)
print('Number_SupportVector:\n', Num_SV)
print('SupportVectors:\n', clf.support_vectors_)
print('Norm between SupportVector and ID_function:\n', Norm_SV_ID)
print('Norm in class0:\n', Norm_SV_ID[Num_SV[0]-10:Num_SV[0]-1])
print('Norm in class1:\n', Norm_SV_ID[Num_SV[0]-1+Num_SV[1]-10:Num_SV[0]-1+Num_SV[1]-1])
print('Norm in class2:\n', Norm_SV_ID[Num_SV[0]+Num_SV[1]-1+Num_SV[2]-10:Num_SV[0]+Num_SV[1]-1+Num_SV[2]-1])







#-----------------------------------f_Enz(t)の線形回帰-----------------------------------------------------#
print('----------------------------------------------------------------------------------------')
print('-----------------------------------f_Enz(t)の線形回帰--------------------------------------')
print('----------------------------------------------------------------------------------------')

model = FMeans_pp(s)
model.fit(eps_Enz, R_Enz)

Xr0 = Xc[model.labels_ == 0,:,:]
wr0 = w_Enz[model.labels_ == 0]
#print('wr0:', wr0.shape)
X0 = Xr0[0,:,:]
w0 = [wr0[0]]*c
for i in range(Xr0.shape[0]-1):
    i += 1
    X0 = np.c_[X0, Xr0[i,:,:]]
    w0 = np.r_[w0, [wr0[i]]*c]
#print('X0:', X0.shape)
#print('w0:', w0.shape)
T0 = X0[0,:]
H0 = X0[1,:]
Enz0 = X0[2,:]
y0 = f_Enz(T0, H0, Enz0)

Xr1 = Xc[model.labels_ == 1,:,:]
wr1 = w_Enz[model.labels_ == 1]
#print('wr1:', wr1.shape)
X1 = Xr1[0,:,:]
w1 = [wr1[0]]*c
for i in range(Xr1.shape[0]-1):
    i += 1
    X1 = np.c_[X1, Xr1[i,:,:]]
    w1 = np.r_[w1, [wr1[i]]*c]
#print('X1:', X1.shape)
#print('w1:', w1.shape)
T1 = X1[0,:]
H1 = X1[1,:]
Enz1 = X1[2,:]
y1 = f_Enz(T1, H1, Enz1)

Xr2 = Xc[model.labels_ == 2,:,:]
wr2 = w_Enz[model.labels_ == 2]
#print('wr2:', wr2.shape)
X2 = Xr2[0,:,:]
w2 = [wr2[0]]*c
for i in range(Xr2.shape[0]-1):
    i += 1
    X2 = np.c_[X2, Xr2[i,:,:]]
    w2 = np.r_[w2, [wr2[i]]*c]
#print('X2:', X2.shape)
#print('w2:', w2.shape)
T2 = X2[0,:]
H2 = X2[1,:]
Enz2 = X2[2,:]
y2 = f_Enz(T2, H2, Enz2)

F = [X0, X1, X2]
L = [y0, y1, y2]
W = [w0, w1, w2]

theta = np.empty((s, n+1))

for i in range(s):
    Fe = sm.add_constant(F[i].T)
    mod_wls = sm.WLS(L[i], Fe, weights=W[i])
    res_wls = mod_wls.fit()
    theta[i,:] = res_wls.params

print('------------------------------------------------------------------------------------------------------------------')
print('[y切片, Tの係数, Hの係数, Enzの係数]:\n', theta)


X_features = np.concatenate([X0, X1, X2], 1)
X_labels = np.concatenate((np.array([0]*X0.shape[1]), np.array([1]*X1.shape[1]), np.array([2]*X2.shape[1])), axis = 0)
clf = SVC(kernel='linear', decision_function_shape='ovo')
clf.fit(X_features.T, X_labels)
Norm_SV_ID = clf.decision_function(clf.support_vectors_)
Num_SV = clf.n_support_

for i in range(s):
    print('Number of label %d : %d' % (i, F[i].shape[1]))

print('X_features:', X_features.shape)
print('X_labels:', X_labels.shape)
print('coef_ID function(T,H,Enz):\n', clf.coef_)
print('intercept_ID function(S):\n', clf.intercept_)
#print('support_index:\n', clf.support_)
print('Number_SupportVector:\n', Num_SV)
print('SupportVectors:\n', clf.support_vectors_)
print('Norm between SupportVector and ID_function:\n', Norm_SV_ID)
print('Norm in class0:\n', Norm_SV_ID[Num_SV[0]-10:Num_SV[0]-1])
print('Norm in class1:\n', Norm_SV_ID[Num_SV[0]-1+Num_SV[1]-10:Num_SV[0]-1+Num_SV[1]-1])
print('Norm in class2:\n', Norm_SV_ID[Num_SV[0]+Num_SV[1]-1+Num_SV[2]-10:Num_SV[0]+Num_SV[1]-1+Num_SV[2]-1])