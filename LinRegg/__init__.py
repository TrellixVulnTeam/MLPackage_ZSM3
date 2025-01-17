import numpy as np
import math
from scipy import linalg
from scipy.stats import norm, t, f, pearsonr
from scipy.sparse.linalg import lsqr


class LinRegg:
    # assumes input is of the form [[x11, x12, x13, ..., x1p], [x21, x22, ..., x2p], [xN1, xN2, ..., xNp]] (numpy array)
    # assumes output is of the form [y1, y2, y2, ... , yN] (numpy array)
    # normalized implies that someone has already turned the input to be of the form [[1, x11, x12, x13, ..., x1p], [1, x21, x22, ..., x2p], [1, xN1, xN2, ..., xNp]]

    # THINGS TO DO LATER:
    # inputArray and outputArray should have the same size
    # check if inputArray is linearly independent [remove 'duplicate']
    def __init__(self, inputArray, outputArray, normalized=False):
        if len(inputArray) != len(outputArray):
            raise Exception('your input size and the output size must match {0}, {1}'.format(len(inputArray), len(outputArray))) 
        if not (normalized):
            self.inputArray = np.insert(inputArray, 0, np.ones(len(inputArray)), axis = 1)
        else:
            self.inputArray = inputArray
        self.outputArray = outputArray
        self.p = len(self.inputArray[0]) - 1
        self.N = len(self.inputArray)
        if outputArray.ndim > 1:
            self.K = len(self.outputArray[0])
        else:
            self.K = 1

#removes the bias term 1 first before standardizing

    def standardizePredictor(self):
        X = np.transpose(np.transpose(self.inputArray)[1:])
        meanInput = np.mean(X ,axis=0)
        self.XMean = meanInput
        stdInput = np.std(X, axis=0)
        self.XStd = stdInput
        standardizedInput = (X - meanInput) / stdInput
        self.inputArray= np.insert(standardizedInput, 0, 1, axis=1)

    def standardizeTest(self, testX):
        standardizedTestX = (testX - self.XMean)/self.XStd
        return np.insert(standardizedTestX, 0, 1, axis=1)


    def RSSSolve(self):
        xTy = np.dot(np.transpose(self.inputArray), self.outputArray)
        matrix = np.dot(np.transpose(self.inputArray), self.inputArray)
        realMatrix = linalg.inv(matrix)
        self.bestFit = np.dot(realMatrix, xTy)
        return self.bestFit

    def calculateResidual(self):
        if not (hasattr(self, 'bestFit')):
            self.RSSSolve()
        testOutput = np.dot(self.inputArray, self.bestFit)
        return self.outputArray - testOutput

    def RSS(self):
        if not (hasattr(self, 'bestFit')):
            self.RSSSolve()
        self.RSSVal = np.dot(self.outputArray - np.dot(self.inputArray, self.bestFit), self.outputArray - np.dot(self.inputArray, self.bestFit))
        return (self.RSSVal)

    def setVariance(self, variance):
        self.variance = variance

    def approximateVariance(self):
        residual = self.calculateResidual()
        self.variance = 1 / (self.N - self.p - 1) * np.trace((np.dot(np.transpose(residual), residual)))
        return self.variance

    # Assumes N (the sample size) is very large
    # checkMatters calculates whether Bi = 0 (and thus the variable doesn't matter) or not
    # Note True does not mean that it matters. It is simply indeterminant
    def zScore(self, index, variance=None):
        if not (hasattr(self, 'bestFit')):
            self.RSSSolve()
        if variance == None:
            if not (hasattr(self, 'variance')):
                self.approximateVariance()
            variance = self.variance
        normalizedStandardDeviationMatrix = linalg.inv(np.dot(np.transpose(self.inputArray), self.inputArray))
        zScore = self.bestFit[index] / (math.sqrt(variance * normalizedStandardDeviationMatrix[index][index]))
        return (zScore)

    def checkMatters(self, index, variance=None, pValue=0.05, tTest=False):
        zScore = self.zScore(index, variance)
        if tTest:
            rv = t(df=len(self.N - self.p - 1))
        else:
            rv = norm()
        p = rv.sf(zScore)
        if p > 1 - (pValue) / 2 or p < (pValue) / 2:
            return False
        else:
            return True

    def bestSubset(self, variance=None, pValue = 0.05, tTest = False):
        subsetLst = []
        for index in range(len(self.inputArray[0])):
            if not(self.checkMatters( index, variance, pValue, tTest)):
                subsetLst.append(index)
        self.bestSubsetList = subsetLst
    
    def bestSubsetSolve(self):
        if not(hasattr(self, 'bestSubsetList')):
            self.bestSubset(variance = None, pValue = 0.05, tTest = False)
        X = self.inputArray[:, self.bestSubsetList]
        xTy = np.dot(np.transpose(X), self.outputArray)
        matrix = np.dot(np.transpose(X), X)
        realMatrix = linalg.inv(matrix)
        self.bestSubsetBestFit = np.dot(realMatrix, xTy)
        
        
            
            

    # assumes 0 is not in excludeLst
    def FTest(self, excludeLst, pValue=0.05):
        subsetInputArray = np.delete(self.inputArray, excludeLst, axis=1)
        subsetLinTest = LinRegg(subsetInputArray, self.outputArray, normalized=True)
        subsetLinTest.RSS()
        if not (hasattr(self, 'RSSVal')):
            self.RSS()
        fNumerator = (subsetLinTest.RSSVal - self.RSSVal) / (self.p - subsetLinTest.p)
        fDenominator = self.RSSVal / (self.N - self.p - 1)
        self.fScore = fNumerator / fDenominator
        rv = f(dfn=self.p - subsetLinTest.p, dfd=self.N - self.p - 1)
        p = rv.sf(self.fScore)
        if p > 1 - (pValue) / 2 or p < (pValue) / 2:
            return True
        else:
            return False

    #An approximation to best fit that uses orthogonalization approximation
    #If decompostion set to true, it will find the QR decompsotion

    def orthogonalizationAlgorithm(self, decomposition = False):
        x = np.transpose(self.inputArray)
        bestFit = np.zeros(self.p+1)
        z = np.ones(self.N)
        zArray = np.zeros(shape = (self.p + 1, self.N))
        x = np.transpose(self.inputArray)
        zArray[0] = z
        bestFit[0] = np.dot(zArray[0], self.outputArray)/np.dot(zArray[0], zArray[0])
        for jj in range(1, self.p + 1):
            z = np.copy(x[jj])
            for ii in range(0, jj):
                z -= (np.dot(zArray[ii], x[jj])/np.dot(zArray[ii], zArray[ii])) * zArray[ii]
            zArray[jj] = z
            bestFit[ii] = (np.dot(zArray[ii], self.outputArray)/np.dot(zArray[ii], zArray[ii]))
        self.orthogonalBestFit = bestFit
        self.orthogonalResiduals = zArray
        if decomposition:
            magnitudes = np.zeros(self.p + 1)
            for ii in range(self.p + 1):
                magnitudes[ii] = linalg.norm(zArray[ii])
            D = np.diag(magnitudes)
            DInv = linalg.inv(D)
            Gamma = np.zeros(shape=(self.p+1, self.p+1))
            #Note Element of Statistical Learning doesn't explain this explicitly: gamma_{i, i} = 1
            Z = np.transpose(zArray)
            for jj in range(1, self.p + 1):
                for ii in range(0, jj):
                    Gamma[ii][jj] = np.dot(zArray[ii], x[jj])/np.dot(zArray[ii], zArray[ii])
            for ii in range(0, self.p + 1):
                Gamma[ii][ii] = 1
            Q = np.dot(Z, DInv)
            R = np.dot(D, Gamma)
            self.QRDecomposition = (Q, R)
        return bestFit

    def orthogonalVarianceEstimate(self, variance=None):
        if not(hasattr(self, 'orthogonalResiduals')):
            self.orthogonalizationAlgorithm()
        if not(hasattr(self, 'variance')):
            self.approximateVariance()
        return self.variance/(np.dot(self.orthogonalResiduals[-1], self.orthogonalResiduals[-1]))

    #for now multi-dimensional ouput assumes one single complexity parameter
    #complexity is the complexity parameter (lambda)
    #highlights the variables with higher variance
    def RSSRidgeSolve(self, complexity):
        if self.outputArray.ndim > 1:
            beta0 = np.mean(self.outputArray, axis=0)
        else:
            beta0 = np.mean(self.outputArray)
        X = np.transpose(np.transpose(self.inputArray)[1:])
        xTy = np.dot(np.transpose(X), self.outputArray)
        matrix = np.dot(np.transpose(X), X) + complexity*np.identity(self.p)
        realMatrix = linalg.inv(matrix)
        Beta = np.dot(realMatrix, xTy)
        self.ridgeBestFit = np.insert(Beta, 0, beta0, axis = 0)
        return self.ridgeBestFit

    #assumes single output learning for now
    #epsilon is so far just random
    #time to change it to multiple output format
    def singleLARAlgorithm(self, y, alpha):
        #helper function
        #assumes elem is not in the lst
        def findIndexInSortedLst(elem, lst):
            val = 0
            while lst != []:
                if elem < lst[0]:
                    return val
                elif elem > lst[-1]:
                    return val + len(lst)-1
                else:
                    half = int(len(lst))/2
                    if elem < lst[half]:
                        lst = lst[:half]
                    elif elem > lst[half]:
                        lst = lst[half+1:]
                        val += half
        X = self.inputArray
        activeXT = np.array([[1]*self.N])
        beta0 = np.mean(y)
        bestFit = np.zeros(1)
        bestFit[0] = beta0
        mostCorrelatedIndices = [0]
        for _ in range(min(self.p, self.N-1)):
            residual = y -np.dot(np.transpose(activeXT), bestFit)
            while True:
                curMaxCor = -1
                maxCorrelatedIndex = None
                XTranspose = X.transpose()
                for jj in range(1, len(XTranspose)):
                    correlation = abs(pearsonr(XTranspose[jj], residual)[0])
                    if correlation > curMaxCor:
                        maxCorrelatedIndex = jj
                        curMaxCor = correlation
                if not maxCorrelatedIndex in mostCorrelatedIndices:
                    place = findIndexInSortedLst(maxCorrelatedIndex, mostCorrelatedIndices)
                    activeXTLst = activeXT.tolist()
                    activeXTLst.insert(place+1, X[:, maxCorrelatedIndex].tolist())
                    activeXT = np.array(activeXTLst)
                    bestFit = np.insert(bestFit, place, 0, axis=1)
                    mostCorrelatedIndices.insert(place, maxCorrelatedIndex)
                    break
                else:
                    delta = np.dot((np.dot(linalg.inv(np.dot(activeXT, np.transpose(activeXT))), activeXT)), residual)
                    bestFit += alpha*delta


                residual = y - np.dot(np.transpose(activeXT), bestFit)
        self.LARBestFit = bestFit
        return self.LARBestFit
    
    def LARAlgorithm(self, alpha=0.1):
        if self.K == 1:
            self.LARBestFit = self.singleLARAlgorithm(y=self.outputArray, alpha=alpha)
        else:
            bestFit = np.zeros(shape=(self.p+1, self.K))
            for ii in range(self.K):
                bestFit[:,ii] = self.singleLARAlgorithm(y=self.outputArray[:,ii], alpha=alpha)
            self.LARBestFit = bestFit


    #same as above but adds the condition that when non-zero coefficient hits zero, drop its variable from the active set of variable
    #Introduce coordinate descent(?)
    def singleLARLassoAlgorithm(self, y, alpha=0.1):
        #helper function
        #assumes elem is not in the lst
        def findIndexInSortedLst(elem, lst):
            val = 0
            while lst != []:
                if elem < lst[0]:
                    return val
                elif elem > lst[-1]:
                    return val + len(lst)-1
                else:
                    half = int(len(lst))/2
                    if elem < lst[half]:
                        lst = lst[:half]
                    elif elem > lst[half]:
                        lst = lst[half+1:]
                        val += half
        X = self.inputArray
        activeXT = np.array([[1]*self.N])
        beta0 = np.mean(y)
        bestFit = np.zeros(1)
        bestFit[0] = beta0
        mostCorrelatedIndices = [0]
        for _ in range(min(self.p, self.N-1)):
            residual = y -np.dot(np.transpose(activeXT), bestFit)
            while True:
                curMaxCor = -1
                maxCorrelatedIndex = None
                XTranspose = X.transpose()
                for jj in range(1, len(XTranspose)):
                    correlation = abs(pearsonr(XTranspose[jj], residual)[0])
                    if correlation > curMaxCor:
                        maxCorrelatedIndex = jj
                        curMaxCor = correlation
                if not maxCorrelatedIndex in mostCorrelatedIndices:
                    place = findIndexInSortedLst(maxCorrelatedIndex, mostCorrelatedIndices)
                    activeXTLst = activeXT.tolist()
                    activeXTLst.insert(place+1, X[:, maxCorrelatedIndex].tolist())
                    activeXT = np.array(activeXTLst)
                    bestFit = np.insert(bestFit, place, 0)
                    mostCorrelatedIndices.insert(place, maxCorrelatedIndex)
                    break
                else:
                    delta = np.dot((np.dot(linalg.inv(np.dot(activeXT, np.transpose(activeXT))), activeXT)), residual)
                    bestFit += alpha*delta
                    jj = 0
                    while jj < len(bestFit):
                        if bestFit[jj] == 0:
                            bestFit = np.delete(bestFit, jj)
                            activeXT = np.delete(activeXT, jj, 0)
                            print('removed: {0}'.format(mostCorrelatedIndices[jj]))
                        jj += 1

                residual = y - np.dot(np.transpose(activeXT), bestFit)
        return bestFit

    def LARLassoAlgorithm(self, alpha=0.1):
        if self.K == 1:
            self.lassoBestFit = self.singleLARLassoAlgorithm(y=self.outputArray, alpha=alpha)
        else:
            bestFit = np.zeros(shape=(self.p+1, self.K))
            for ii in range(self.K):
                bestFit[:,ii] = self.singleLARLassoAlgorithm(y=self.outputArray[:,ii], alpha=alpha)
            self.lassoBestFit = bestFit



    def singlePrincipalComponentRegression(self, y):
        X = self.inputArray
        #only interested in a columns of eigenvectors, vh
        vh = linalg.svd(X)[2]
        bestFit = np.zeros(self.p+1)
        for v in vh:
            z = np.dot(X, v)
            theta = np.dot(z, y)/np.dot(z, z)
            bestFit +=  theta*v
        return bestFit

    def principalComponentRegression(self):
        if self.K == 1:
            self.PCRBestFit = self.singlePrincipalComponentRegression(y = self.outputArray)
        else:
            bestFit = np.zeros(shape = (self.p+1, self.K))
            for ii in range(self.K):
                bestFit[:,ii] = self.singlePrincipalComponentRegression(y = self.outputArray[:,ii])
            self.PCRBestFit = bestFit


    #Follows the book but the coefficients of the best fit is obtained with the algorithm described in wikipedia
    #
    def singlePartialLeastSquares(self, y, M):
        if M == None or M > self.p:
            M = self.p
        X = np.copy(self.inputArray)[:,1:]
        yPred = np.mean(y)*np.ones(self.N)
        #Solves XB = yPred
        #For now, forgets the b term.
        xTy = np.dot(np.transpose(X), yPred)
        matrix = np.dot(np.transpose(X), X)
        realMatrix = linalg.inv(matrix)
        B = np.dot(realMatrix, xTy)
        #b0 = np.mean(y)
        Phi = np.zeros(shape=(self.p, M))
        Z = np.zeros(shape=(self.N, M))
        P = np.zeros(shape = (self.p, M))
        Theta = np.zeros(M)
        for ii in range(0, M):
            z = np.zeros(self.N)
            for jj in range(self.p):
                phi = np.dot(X[:, jj], y)
                Phi[jj][ii] = phi
                z += phi*X[:, jj]
            theta = np.dot(z, y)/np.dot(z, z)
            Theta[ii] = theta
            Z[:,ii] = z
            p = np.dot(np.transpose(X), z)
            P[:,ii] = p
            yPred += theta*z
            for jj in range(self.p):
                X[:,jj] -= (np.dot(z, X[:,jj])/np.dot(z, z))*z
        b0 = Theta[0] - np.dot(np.transpose(P[:,0]), B)
        bestFit = np.insert(B, 0, b0)
        return bestFit
    
    def partialLeastSquares(self, M=None):
        if self.K == 1:
            self.PLSBestFit = self.singlePartialLeastSquares(y=self.outputArray, M=M)
        else:
            bestFit = np.zeros(shape = (self.p+1, self.K))
            for ii in range(self.K):
                bestFit[:,ii] = self.singlePartialLeastSquares(y = self.outputArray[:,ii], M=M)
            self.PLSBestFit = bestFit



        

    def incrementalForwardStagewise(self, eps = 0.01):
        residual = self.outputArray
        bestFit = np.zeros(self.p)
        X = self.inputArray
        while True:
            mostCorrelatedIndex = 0
            maxCorrelation = abs(pearsonr(residual, X[:, 0])[0])
            for ii in range(self.p):
                correlation = abs(pearsonr(residual, X[:,ii])[0])
                if correlation > maxCorrelation:
                    maxCorrelatedIndex = ii
                    maxCorrelation = correlation
            if maxCorrelation == 0:
                break
            else:
                delta = eps* np.sign(np.dot(X[:, mostCorrelatedIndex], residual))
                bestFit[maxCorrelatedIndex] += delta
                residual -= delta * X[:, mostCorrelatedIndex]
        self.incrementalForwardStagewiseBestFit = bestFit
        return self.incrementalForwardStagewiseBestFit


    #OVERALL SUMMARY:
    #Ridge is generally the most preferable for minimizing prediction errors
    #PLS, PCR and Ridge are fairly similar
    #Lasso is somewhere between Ridge and best subsets (enjoys favourable properties of both)



