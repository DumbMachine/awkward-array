#!/usr/bin/env python

# Copyright (c) 2018, DIANA-HEP
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
# 
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
# 
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
try:
    __import__('pkg_resources').declare_namespace(__name__)
except ImportError:
    __path__ = __import__('pkgutil').extend_path(__path__, __name__)

from awkward.array.chunked import ChunkedArray
from awkward.array.chunked import AppendableArray
from awkward.array.indexed import IndexedArray, SparseArray
# from awkward_numba.array.jagged import JaggedArrayNumba as JaggedArray
from awkward.array.jagged import JaggedArray
from awkward.array.masked import MaskedArray, BitMaskedArray, IndexedMaskedArray
from awkward.array.objects import Methods, ObjectArray, StringArray
from awkward.array.table import Table
from awkward.array.union import UnionArray
from awkward.array.virtual import VirtualArray

import numba
import awkward

from awkward.generate import fromiter, fromiterchunks
from awkward.persist import serialize, deserialize, save, load, hdf5


@staticmethod
@numba.jit(nopython=True)
def _argminmax_fillmin(starts, stops, content, output):
    k = 0
    for i in range(len(starts)):
        if stops[i] != starts[i]:
            best = content[starts[i]]
            bestj = 0
            for j in range(starts[i] + 1, stops[i]):
                if content[j] < best:
                    best = content[j]
                    bestj = j - starts[i]
            output[k] = bestj
            k += 1

@staticmethod            
@numba.jit(nopython=True)
def _argminmax_fillmax(starts, stops, content, output):
    k = 0
    for i in range(len(starts)):
        if stops[i] != starts[i]:
            best = content[starts[i]]
            bestj = 0
            for j in range(starts[i] + 1, stops[i]):
                if content[j] > best:
                    best = content[j]
                    bestj = j - starts[i]
            output[k] = bestj
            k += 1


def _argminmax_general_numba(self, ismin):
    if len(self._content.shape) != 1:
        raise ValueError("cannot compute arg{0} because content is not one-dimensional".format("min" if ismin else "max"))

    # subarray with counts > 0 --> counts = 1
    counts = (self.counts != 0).astype(self.INDEXTYPE)

    # offsets for these 0 or 1 counts (involves a cumsum)
    offsets = awkward.array.jagged.counts2offsets(counts)
    # starts and stops derived from offsets and reshaped to original starts and stops (see specification)
    starts, stops = offsets[:-1], offsets[1:]
    starts.reshape(self._starts.shape[:-1] + (-1,))
    stops.reshape(self._starts.shape[:-1] + (-1,))

    # content to fit the new offsets
    content = awkward.util.numpy.empty(offsets[-1], dtype=self.INDEXTYPE)
    
    # fill the new content
    if ismin:
        self._argminmax_fillmin(self._starts.reshape(-1), self._stops.reshape(-1), self._content, content)
    else:
        self._argminmax_fillmax(self._starts.reshape(-1), self._stops.reshape(-1), self._content, content)
    return self.copy(starts=starts, stops=stops, content=content)

JaggedArray._argminmax_fillmax = _argminmax_fillmax
JaggedArray._argminmax_fillmin = _argminmax_fillmin
JaggedArray._argminmax_general_numba = _argminmax_general_numba

__all__ = ["ChunkedArray", "AppendableArray", "IndexedArray", "SparseArray", "JaggedArray", "MaskedArray", "BitMaskedArray", "IndexedMaskedArray", "Methods", "ObjectArray", "Table", "UnionArray", "VirtualArray", "StringArray", "fromiter", "fromiterchunks", "serialize", "deserialize", "save", "load", "hdf5"]
