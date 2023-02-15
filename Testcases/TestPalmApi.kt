package ru.yandex.market.tpl.e2e.data.remote

import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.Path
import retrofit2.http.Query
import ru.yandex.market.tpl.e2e.data.feature.testcase.TestCaseDto

interface TestPalmApi {
    @GET("testcases/{projectId}")
    suspend fun getTestCases(
        @Header("Authorization") token: String,
        @Path("projectId") projectId: String,
        @Query("expression") filterExpression: String,
    ): List<TestCaseDto>
}