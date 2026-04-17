import React, { useState, useCallback } from 'react';
import api from './client';

export function useGenerateReview() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);

  const generate = useCallback(async (params) => {
    setLoading(true);
    setError(null);

    try {
      const result = await api.generateReview(params);
      setData(result);
      return result;
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Unknown error';
      setError(errorMsg);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return { loading, error, data, generate };
}

export function useIndexStatus() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const result = await api.getIndexStatus();
      setStatus(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load index status');
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    refresh();
  }, [refresh]);

  return { status, loading, error, refresh };
}

export function useSystemConfig() {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  React.useEffect(() => {
    async function loadConfig() {
      try {
        const result = await api.getConfig();
        setConfig(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load config');
      } finally {
        setLoading(false);
      }
    }

    loadConfig();
  }, []);

  return { config, loading, error };
}
