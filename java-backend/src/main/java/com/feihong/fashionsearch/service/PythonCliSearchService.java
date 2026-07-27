package com.feihong.fashionsearch.service;

import java.util.List;

import org.springframework.stereotype.Service;

import com.feihong.fashionsearch.dto.SearchRequest;
import com.feihong.fashionsearch.dto.SearchResult;

@Service
public class PythonCliSearchService implements SearchService {
    private final PythonSearchAdapter adapter;

    public PythonCliSearchService(PythonSearchAdapter adapter) {
        this.adapter = adapter;
    }

    @Override
    public List<SearchResult> search(SearchRequest request) {
        return adapter.search(request.query().trim(), request.resolvedTopK());
    }
}
