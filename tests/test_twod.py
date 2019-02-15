import numpy as np
import treecorr
from scipy.spatial.distance import pdist, squareform

def get_correlation_length_matrix(size, e1, e2):

    if abs(e1)>1:
        e1 = 0
    if abs(e2)>1:
        e2 = 0
    e = np.sqrt(e1**2 + e2**2)
    q = (1-e) / (1+e)
    phi = 0.5 * np.arctan2(e2,e1)
    rot = np.array([[np.cos(phi), np.sin(phi)],
                    [-np.sin(phi), np.cos(phi)]])
    ell = np.array([[size**2, 0],
                    [0, (size * q)**2]])
    L = np.dot(rot.T, ell.dot(rot))
    return L

def corr2d(x, y, kappa1, kappa2, w=None, rmax=1., bins=513, return_counts=False):

    hrange = [ [-rmax,rmax], [-rmax,rmax] ]
    
    ind = np.linspace(0,len(x)-1,len(x)).astype(int)
    i1, i2 = np.meshgrid(ind,ind)
    i1 = i1.reshape(len(x)**2)
    i2 = i2.reshape(len(x)**2)

    yshift = y[i2]-y[i1]
    xshift = x[i2]-x[i1]
    if w is not None:
        ww = w[i1] * w[i2]
    else:
        ww = None

    counts = np.histogram2d(xshift, yshift, bins=bins, range=hrange, weights=ww)[0]

    vv = np.real(kappa1[i1] * kappa2[i2])
    if ww is not None: vv *= ww

    xi = np.histogram2d(xshift, yshift, bins=bins, range=hrange, weights=vv)[0]

    # Note: This calculation includes the "pairs" where both objects are the same as part
    # of the zero lag bin.  We don't want that, so subtract it off.
    mid = bins // 2
    if w is None:
        auto = np.real(np.sum(kappa1 * kappa2))
        sumww = len(kappa1)
    else:
        auto = np.real(np.sum(kappa1 * kappa2 * w**2))
        sumww = np.sum(w**2)
    xi[mid,mid] -= auto
    counts[mid,mid] -= sumww

    xi /= counts
    if return_counts:
        return xi.T, counts.T
    else:
        return xi.T


def test_twod():

    # N random points in 2 dimensions
    np.random.seed(42)
    N = 1000
    x = np.random.uniform(-10, 10, N)
    y = np.random.uniform(-10, 10, N)
    
    # Give the points a multivariate Gaussian random field for kappa and gamma
    L1 = [[0.33, 0.09], [-0.01, 0.26]]  # Some arbitrary correlation matrix
    invL1 = np.linalg.inv(L1)
    dists = pdist(np.array([x,y]).T, metric='mahalanobis', VI=invL1)
    K = np.exp(-0.5 * dists**2)
    K = squareform(K)
    np.fill_diagonal(K, 1.)

    A = 2.3
    kappa = np.random.multivariate_normal(np.zeros(N), K*(A**2))

    # Add some noise
    sigma = A/10.
    kappa += np.random.normal(scale=sigma, size=N)
    kappa_err = np.ones_like(kappa) * sigma

    # Make gamma too
    gamma1 = np.random.multivariate_normal(np.zeros(N), K*(A**2))
    gamma1 += np.random.normal(scale=sigma, size=N)
    gamma2 = np.random.multivariate_normal(np.zeros(N), K*(A**2))
    gamma2 += np.random.normal(scale=sigma, size=N)
    gamma = gamma1 + 1j * gamma2
    gamma_err = kappa_err

    # Calculate the 2D correlation using brute force
    max_sep = 10.
    nbins = 21
    xi_brut = corr2d(x, y, kappa, kappa, w=None, rmax=max_sep, bins=nbins)

    cat1 = treecorr.Catalog(x=x, y=y, k=kappa, g1=gamma1, g2=gamma2)
    kk = treecorr.KKCorrelation(min_sep=0., max_sep=max_sep, nbins=nbins, metric='TwoD', bin_slop=0)

    # First the simplest case to get right: cross correlation of the catalog with itself.
    kk.process(cat1, cat1, metric='TwoD')

    print('max abs diff = ',np.max(np.abs(kk.xi - xi_brut)))
    print('max rel diff = ',np.max(np.abs(kk.xi - xi_brut)/np.abs(kk.xi)))
    np.testing.assert_allclose(kk.xi, xi_brut, atol=1.e-7)

    # Auto-correlation should do the same thing.
    kk.process(cat1, metric='TwoD')
    print('max abs diff = ',np.max(np.abs(kk.xi - xi_brut)))
    print('max rel diff = ',np.max(np.abs(kk.xi - xi_brut)/np.abs(kk.xi)))
    np.testing.assert_allclose(kk.xi, xi_brut, atol=1.e-7)

    # Repeat with weights.
    xi_brut = corr2d(x, y, kappa, kappa, w=1./kappa_err**2, rmax=max_sep, bins=nbins)
    cat2 = treecorr.Catalog(x=x, y=y, k=kappa, g1=gamma1, g2=gamma2, w=1./kappa_err**2)
    kk = treecorr.KKCorrelation(min_sep=0., max_sep=max_sep, nbins=nbins, metric='TwoD', bin_slop=0)
    kk.process(cat2, cat2, metric='TwoD')

    print('max abs diff = ',np.max(np.abs(kk.xi - xi_brut)))
    print('max rel diff = ',np.max(np.abs(kk.xi - xi_brut)/np.abs(kk.xi)))
    np.testing.assert_allclose(kk.xi, xi_brut, atol=1.e-7)

    kk.process(cat2, metric='TwoD')
    np.testing.assert_allclose(kk.xi, xi_brut, atol=1.e-7)

    # Check GG
    xi_brut = corr2d(x, y, gamma, np.conj(gamma), rmax=max_sep, bins=nbins)
    gg = treecorr.GGCorrelation(min_sep=0., max_sep=max_sep, nbins=nbins, metric='TwoD', bin_slop=0)
    gg.process(cat1, metric='TwoD')
    print('max abs diff = ',np.max(np.abs(gg.xip - xi_brut)))
    print('max rel diff = ',np.max(np.abs(gg.xip - xi_brut)/np.abs(gg.xip)))
    np.testing.assert_allclose(gg.xip, xi_brut, atol=1.e-7)

    xi_brut = corr2d(x, y, gamma, np.conj(gamma), w=1./kappa_err**2, rmax=max_sep, bins=nbins)
    gg = treecorr.GGCorrelation(min_sep=0., max_sep=max_sep, nbins=nbins, metric='TwoD', bin_slop=0)
    gg.process(cat2, metric='TwoD')
    print('max abs diff = ',np.max(np.abs(gg.xip - xi_brut)))
    print('max rel diff = ',np.max(np.abs(gg.xip - xi_brut)/np.abs(gg.xip)))
    np.testing.assert_allclose(gg.xip, xi_brut, atol=1.e-7)

    # Check NK
    xi_brut = corr2d(x, y, np.ones_like(kappa), kappa, rmax=max_sep, bins=nbins)
    nk = treecorr.NKCorrelation(min_sep=0., max_sep=max_sep, nbins=nbins, metric='TwoD', bin_slop=0)
    nk.process(cat1, cat1, metric='TwoD')
    print('max abs diff = ',np.max(np.abs(nk.xi - xi_brut)))
    print('max rel diff = ',np.max(np.abs(nk.xi - xi_brut)/np.abs(nk.xi)))
    np.testing.assert_allclose(nk.xi, xi_brut, atol=1.e-7)

    xi_brut = corr2d(x, y, np.ones_like(kappa), kappa, w=1./kappa_err**2, rmax=max_sep, bins=nbins)
    nk = treecorr.NKCorrelation(min_sep=0., max_sep=max_sep, nbins=nbins, metric='TwoD', bin_slop=0)
    nk.process(cat2, cat2, metric='TwoD')
    print('max abs diff = ',np.max(np.abs(nk.xi - xi_brut)))
    print('max rel diff = ',np.max(np.abs(nk.xi - xi_brut)/np.abs(nk.xi)))
    np.testing.assert_allclose(nk.xi, xi_brut, atol=1.e-7)

    # Check NN
    xi_brut, counts = corr2d(x, y, np.ones_like(kappa), np.ones_like(kappa),
                             rmax=max_sep, bins=nbins, return_counts=True)
    nn = treecorr.NNCorrelation(min_sep=0., max_sep=max_sep, nbins=nbins, metric='TwoD', bin_slop=0)
    nn.process(cat1, metric='TwoD')
    print('max abs diff = ',np.max(np.abs(nn.npairs - counts)))
    print('max rel diff = ',np.max(np.abs(nn.npairs - counts)/np.abs(nn.npairs)))
    np.testing.assert_allclose(nn.npairs, counts, atol=1.e-7)

    xi_brut, counts = corr2d(x, y, np.ones_like(kappa), np.ones_like(kappa),
                             w=1./kappa_err**2, rmax=max_sep, bins=nbins, return_counts=True)
    nn = treecorr.NNCorrelation(min_sep=0., max_sep=max_sep, nbins=nbins, metric='TwoD', bin_slop=0)
    nn.process(cat2, metric='TwoD')
    print('max abs diff = ',np.max(np.abs(nn.weight - counts)))
    print('max rel diff = ',np.max(np.abs(nn.weight - counts)/np.abs(nn.weight)))
    np.testing.assert_allclose(nn.weight, counts, atol=1.e-7)

    # The other two, NG and KG can't really be checked with the brute force
    # calculator we have here, so we're counting on the above being a sufficient
    # test of all aspects of the twod binning.  I think that it is sufficient, but I
    # admit I would prefer if we had a real test of these other two pairs, along with
    # xi- for GG.

    
if __name__ == '__main__':
    test_twod()