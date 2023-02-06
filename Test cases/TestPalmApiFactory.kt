package ru.yandex.market.tpl.e2e.data.remote

import com.squareup.moshi.Moshi
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory
import retrofit2.create

class TestPalmApiFactory constructor(private val moshi: Moshi, private val configuration: Configuration) {

    fun create(): TestPalmApi {
        return Retrofit.Builder()
            .baseUrl(configuration.baseUrl)
            .addConverterFactory(MoshiConverterFactory.create(moshi))
            .build()
            .create()
    }

    data class Configuration(val baseUrl: String)
}