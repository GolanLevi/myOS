import { useState, useEffect, useCallback } from 'react';
import { apiGet, apiPatch, apiPost, apiDelete } from '../lib/apiClient.js';

const METHOD_MAP = {
  get:    apiGet,
  post:   apiPost,
  patch:  apiPatch,
  delete: apiDelete,
};

export function useApi(url, { immediate = true, params = {} } = {}) {
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(immediate);
  const [error,   setError]   = useState(null);

  const fetch = useCallback(async (extraParams = {}) => {
    setLoading(true);
    setError(null);
    try {
      const { data: res } = await apiGet(url, { params: { ...params, ...extraParams } });
      setData(res);
      return res;
    } catch (err) {
      setError(err.response?.data?.message || err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [url, JSON.stringify(params)]);

  useEffect(() => {
    if (immediate) fetch();
  }, [immediate, fetch]);

  return { data, loading, error, refresh: fetch, setData };
}

export function useMutation(method, url) {
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);

  const apiFn = METHOD_MAP[method.toLowerCase()] || apiPost;

  const mutate = useCallback(async (body, urlSuffix = '') => {
    setLoading(true);
    setError(null);
    const fullUrl = `${url}${urlSuffix}`;
    try {
      const { data } = method.toLowerCase() === 'delete'
        ? await apiDelete(fullUrl)
        : await apiFn(fullUrl, body);
      return data;
    } catch (err) {
      const msg = err.response?.data?.message || err.message;
      setError(msg);
      throw new Error(msg);
    } finally {
      setLoading(false);
    }
  }, [method, url]);

  return { mutate, loading, error };
}
