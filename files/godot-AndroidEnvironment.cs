using System;
using System.Collections.Generic;
using System.Net;
using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;
using System.Threading;

// See 'mono/sdks/android/managed/fake-monodroid.cs' and 'xamarin-android/src/Mono.Android/Android.Runtime/AndroidEnvironment.cs'

namespace Android.Runtime
{
    public static class AndroidEnvironment
    {
        public const string AndroidLogAppName = "Mono.Android";

        static object lock_ = new object();

        [DllImport("__Internal", CallingConvention = CallingConvention.Cdecl)]
        internal extern static void monodroid_free(IntPtr ptr);

        [DllImport("__Internal", CallingConvention = CallingConvention.Cdecl)]
        static extern IntPtr _monodroid_timezone_get_default_id();

        [DllImport("__Internal", CallingConvention = CallingConvention.Cdecl)]
        static extern int _monodroid_getifaddrs(out IntPtr ifap);

        [DllImport("__Internal", CallingConvention = CallingConvention.Cdecl)]
        static extern void _monodroid_freeifaddrs(IntPtr ifap);

        static string GetDefaultTimeZone()
        {
            IntPtr id = _monodroid_timezone_get_default_id();

            try
            {
                return Marshal.PtrToStringAnsi(id);
            }
            finally
            {
                monodroid_free(id);
            }
        }

        static SynchronizationContext GetDefaultSyncContext()
        {
            // Not needed
            return null;
        }

        static IWebProxy GetDefaultProxy()
        {
            // Not needed
            return null;
        }

        static int GetInterfaceAddresses(out IntPtr ifap)
        {
            return _monodroid_getifaddrs(out ifap);
        }

        static void FreeInterfaceAddresses(IntPtr ifap)
        {
            _monodroid_freeifaddrs(ifap);
        }

        static void DetectCPUAndArchitecture(out ushort builtForCPU, out ushort runningOnCPU, out bool is64bit)
        {
            // Not needed (For now? The BCL code that uses the result is commented...)
            builtForCPU = 0;
            runningOnCPU = 0;
            is64bit = Environment.Is64BitProcess;
        }

        static bool TrustEvaluateSsl(List<byte[]> certsRawData)
        {
            // This is legacy. Not needed as BTLS is used by default instead.
            throw new NotImplementedException();
        }

        [MethodImpl(MethodImplOptions.InternalCall)]
        static extern bool _gd_mono_init_cert_store();

        [MethodImpl(MethodImplOptions.InternalCall)]
        static extern byte[] _gd_mono_android_cert_store_lookup(string alias);

        static bool certStoreInitOk = false;

        static void InitCertStore()
        {
            if (certStoreInitOk)
                return;

            lock (lock_)
            {
                certStoreInitOk = _gd_mono_init_cert_store();
            }
        }

        static byte[] CertStoreLookup(long hash, bool userStore)
        {
            InitCertStore();

            if (!certStoreInitOk)
                return null;

            string alias = string.Format("{0}:{1:x8}.0", userStore ? "user" : "system", hash);

            return _gd_mono_android_cert_store_lookup(alias);
        }
    }
}
