package com.feihong.fashionsearch.common;

import java.util.stream.Collectors;

import jakarta.validation.ConstraintViolationException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import com.feihong.fashionsearch.exception.PythonJsonParseException;
import com.feihong.fashionsearch.exception.PythonNonZeroExitException;
import com.feihong.fashionsearch.exception.PythonProcessStartException;
import com.feihong.fashionsearch.exception.PythonSearchInterruptedException;
import com.feihong.fashionsearch.exception.PythonSearchTimeoutException;
import com.feihong.fashionsearch.exception.SearchServiceException;

@RestControllerAdvice
public class GlobalExceptionHandler {
    private static final Logger log =
            LoggerFactory.getLogger(GlobalExceptionHandler.class);

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ApiResponse<Void>> handleValidation(
            MethodArgumentNotValidException exception
    ) {
        String message = exception.getBindingResult().getFieldErrors().stream()
                .map(error -> error.getField() + ": " + error.getDefaultMessage())
                .collect(Collectors.joining("; "));
        return ResponseEntity.badRequest().body(ApiResponse.error(message));
    }

    @ExceptionHandler(ConstraintViolationException.class)
    public ResponseEntity<ApiResponse<Void>> handleConstraintViolation(
            ConstraintViolationException exception
    ) {
        String message = exception.getConstraintViolations().stream()
                .map(violation -> "limit: " + violation.getMessage())
                .distinct()
                .collect(Collectors.joining("; "));
        return ResponseEntity.badRequest().body(ApiResponse.error(message));
    }

    @ExceptionHandler(PythonSearchTimeoutException.class)
    public ResponseEntity<ApiResponse<Void>> handleTimeout(
            PythonSearchTimeoutException exception) {
        return response(HttpStatus.GATEWAY_TIMEOUT, exception);
    }

    @ExceptionHandler({
            PythonProcessStartException.class,
            PythonNonZeroExitException.class,
            PythonJsonParseException.class
    })
    public ResponseEntity<ApiResponse<Void>> handleBadGateway(
            SearchServiceException exception) {
        return response(HttpStatus.BAD_GATEWAY, exception);
    }

    @ExceptionHandler(PythonSearchInterruptedException.class)
    public ResponseEntity<ApiResponse<Void>> handleInterrupted(
            PythonSearchInterruptedException exception) {
        return response(HttpStatus.SERVICE_UNAVAILABLE, exception);
    }

    @ExceptionHandler(SearchServiceException.class)
    public ResponseEntity<ApiResponse<Void>> handleSearchService(
            SearchServiceException exception) {
        return response(HttpStatus.BAD_GATEWAY, exception);
    }

    private ResponseEntity<ApiResponse<Void>> response(
            HttpStatus status, SearchServiceException exception) {
        log.warn("event=request_failed status={} errorType={}",
                status.value(), exception.getClass().getSimpleName());
        return ResponseEntity.status(status)
                .body(ApiResponse.error(exception.getMessage()));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ApiResponse<Void>> handleUnexpected(Exception exception) {
        log.error("event=request_failed status=500 errorType={}",
                exception.getClass().getSimpleName());
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(ApiResponse.error("An unexpected server error occurred."));
    }
}
