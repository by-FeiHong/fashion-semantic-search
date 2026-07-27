package com.feihong.fashionsearch.service;

import java.util.List;

import com.feihong.fashionsearch.dto.SearchRequest;
import com.feihong.fashionsearch.dto.SearchResult;

public interface SearchService {
    List<SearchResult> search(SearchRequest request);
}
