# ============================================================================
# R8 / ProGuard 规则（release 已开启 isMinifyEnabled + isShrinkResources）
# 目标：在压缩/混淆下保证 kotlinx.serialization 反射、Retrofit 接口、Room、
# Hilt 与所有网络 DTO 正常工作。规则偏保守以确保正确性优先。
# ============================================================================

-keepattributes *Annotation*, InnerClasses, Signature, Exceptions, EnclosingMethod

# ---- kotlinx.serialization（官方推荐规则）-------------------------------------
-dontnote kotlinx.serialization.**
-keepclassmembers class kotlinx.serialization.json.** {
    *** Companion;
}
-keepclasseswithmembers class kotlinx.serialization.json.** {
    kotlinx.serialization.KSerializer serializer(...);
}

# 保留所有 @Serializable 类的 Companion 与 serializer()
-if @kotlinx.serialization.Serializable class **
-keepclassmembers class <1> {
    static <1>$Companion Companion;
}
-if @kotlinx.serialization.Serializable class ** {
    static **$* *;
}
-keepclassmembers class <2>$<3> {
    kotlinx.serialization.KSerializer serializer(...);
}
-if @kotlinx.serialization.Serializable class ** {
    public static ** INSTANCE;
}
-keepclassmembers class <1> {
    public static <1> INSTANCE;
    kotlinx.serialization.KSerializer serializer(...);
}

# 本应用所有网络 DTO 直接整体保留（含字段名，serialization 依赖字段名）
-keep,includedescriptorclasses class com.lovejournal.app.data.remote.dto.** { *; }
-keepclassmembers class com.lovejournal.app.data.remote.dto.** { *; }

# Retrofit 接口（保留泛型签名供反射解析返回类型）
-keep,allowobfuscation interface com.lovejournal.app.data.remote.api.** { *; }

# ---- Retrofit / OkHttp（多数随库自带 consumer 规则，这里补强）-----------------
-dontwarn okhttp3.**
-dontwarn okio.**
-dontwarn retrofit2.**
-keepattributes RuntimeVisibleAnnotations, RuntimeVisibleParameterAnnotations
-keepclasseswithmembers class * {
    @retrofit2.http.* <methods>;
}

# ---- Room ------------------------------------------------------------------
-keep class * extends androidx.room.RoomDatabase { <init>(); }
-dontwarn androidx.room.paging.**

# ---- Hilt / Dagger（随库自带规则，补一条安全网）-------------------------------
-keep,allowobfuscation @interface dagger.hilt.android.lifecycle.HiltViewModel

# ---- Firebase Messaging ----------------------------------------------------
-keep class com.google.firebase.** { *; }
-dontwarn com.google.firebase.**

# ---- Glance / Coil 等附带 consumer 规则，无需额外配置 -------------------------
